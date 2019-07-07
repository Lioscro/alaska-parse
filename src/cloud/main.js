/* Testing */
Parse.Cloud.define('hello', function(req, res) {
  return 'Hi';
});

Parse.Cloud.job('testjob', function(request, status) {
  console.log('running test job');
  status.success('Success');
});

/* Cloud function to fetch next item in the queue. */
Parse.Cloud.define('dequeue', async (request) => {
  const query = new Parse.Query('Job');
  query.exists('queuePosition');
  query.ascending('queuePosition');

  // Find first.
  const result = await query.first();

  return result;
});

/* Cloud function to fetch dictionary of organisms. */
Parse.Cloud.define('getOrganismsDict', async (request) => {
  const query = new Parse.Query('Organism');

  // Find all.
  const results = await query.find();
  console.log(results);

  var organisms = {};
  for (var i = 0; i < results.length; i++) {
    var object = results[i];
    var genus = object.get('genus');
    var species = object.get('species');
    console.log(genus, species);

    if (!(genus in organisms)) {
      organisms[genus] = {};
    }
    if (!(species in organisms[genus])) {
      organisms[genus][species] = {};
    }

    // Get all reference versions.
    var references = await object.relation('references').query().find();
    console.log(references);
    for (var j = 0; j < references.length; j++) {
      var reference = references[j];
      var version = reference.get('version');
      organisms[genus][species][version] = reference.id;
    }
  }

  return organisms;
});

/* Job to scan for new references. */
Parse.Cloud.job('Reference: scan for new', async function(request, status) {
  console.log('starting scan');
  var response = await Parse.Cloud.httpRequest({
    method: 'POST',
    url: 'http://webhook:5000/reference/new',
    followRedirects: true
  });
  console.log('done');
});

/* Job to build unbuilt references. */
Parse.Cloud.job('Reference: build unbuilt indices', function(request, status) {
  Parse.Cloud.httpRequest({
    method: 'POST',
    url: 'http://webhook:5000/reference/build',
    followRedirects: true
  }).then(function(httpResponse) {
    console.log(httpResponse.data);
  }, function(httpResponse) {
    console.error('Request failed with response code ' + httpResponse.status);
  });
  status.success();
});

/* Initialize new project. */
Parse.Cloud.define('newProject', async (request) => {
  var Project = Parse.Object.extend('Project');
  var project = new Project();
  await project.save({'files': {}, 'progress': 'init', 'metadata': {}, 'formInput': {}});
  console.log(project);

  // Send new project request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: 'http://webhook:5000/project/' + project.id + '/initialize',
      followRedirects: true,
    });
  } catch (e) {
    await project.destroy();
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if ('result' in data) {
    await project.save(data.result);
    return project;
  } else if ('error' in data) {
    // Remove project.
    await project.destroy();
    return data;
  } else {
    return {'error': 'unknown response'};
  }
});

Parse.Cloud.define('getReads', async (request) => {
  var objectId = request.params.objectId;

  // Send project reads request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: 'http://webhook:5000/project/' + objectId + '/reads',
      followRedirects: true,
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  } else {
    return data.result;
  }
});

/* Get md5 checksum. */
Parse.Cloud.define('getMd5', async (request) => {
  var path = request.params.path;

  // Send project reads request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: 'http://webhook:5000/read/md5',
      followRedirects: true,
      params: {'path': path}
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  } else {
    return data.result;
  }
});

/* Set samples. */
Parse.Cloud.define('setSamples', async (request) => {
  var objectId = request.params.objectId;
  var samples = request.params.samples;

  // Get project object.
  var query = new Parse.Query('Project');
  var project = await query.get(objectId);

  // Remove all existing samples from this project.
  var relation = project.relation('samples');
  var related_samples = await relation.query().find();
  for (var i = 0; i < related_samples.length; i++) {
    related_samples[i].destroy();
  }

  var Read = Parse.Object.extend('Read');
  var Sample = Parse.Object.extend('Sample');
  var new_reads = [];
  var new_samples = [];
  try {
    for (sample_name in samples) {
      console.log(sample_name);
      var sample = samples[sample_name];

      var new_sample = new Sample({'name': sample_name, 'metadata': {}, 'formInput': {}});
      new_samples.push(new_sample);
      new_sample.set('files', {});
      new_sample.relation('projects').add(project);

      for (var i = 0; i < sample.length; i++) {
        var read = sample[i];

        // Validate that they have the required fields.
        if (!('path' in read) || !('size' in read) || !('md5Checksum' in read)) {
          return {'error': 'path, size or md5Checksum missing'};
        }

        // Save the read with these options.
        var new_read = new Read(read);
        new_reads.push(new_read);
        new_read.set('sample', new_sample);
        await new_read.save();
        console.log(new_read);
        new_sample.relation('reads').add(new_read);
        await new_sample.save();
        new_sample = await new_sample.fetch();
      }

      project.relation('samples').add(new_sample);
      await project.save();
      project = await project.fetch();

      // Make directories.
      var response = await Parse.Cloud.httpRequest({
        method: 'POST',
        url: 'http://webhook:5000/project/' + project.id + '/sample/' + new_sample.id + '/initialize' ,
        followRedirects: true,
        params: {'name': sample_name}
      });
      var data = response.data;

      console.log(data);

      if (!('result' in data) ){
        throw data;
      } else {
        new_sample.save(data.result);
      }
    }

    // Set project progress to 'meta'
    await project.save({'progress': 'meta'});

    return {'reads': new_reads, 'samples': new_samples};
  } catch (e) {
    // If an error occured, destoy all new reads and samples.
    for (var i = 0; i < new_reads.length; i++) {
      new_reads[i].destroy();
    }
    for (var i = 0; i < new_samples.length; i++) {
      new_samples[i].destroy();
    }

    throw e;
  }
});

Parse.Cloud.define('sampleCitation', async (request) => {
  const objectId = request.params.objectId;

  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: `http://webhook:5000/sample/${objectId}/citation`,
      followRedirects: true,
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data)) {
    throw data;
  }

  return data.result;
});

/* Start project.. */
Parse.Cloud.define('startProject', async (request) => {
  var objectId = request.params.objectId;

  // Get the project.
  var query = new Parse.Query('Project');
  var project = await query.get(objectId);

  var config = await Parse.Config.get();
  var progress = config.get('progress');

  // Finalize project first.
  await project.save({'progress': 'finalized',
                      'finalized': true,
                      'oldProgress': progress.finalized,
                      'progress': 'queued'});

  // Write citation.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: `http://webhook:5000/project/${objectId}/citation`,
      followRedirects: true
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  }

  // Change ftp home directory.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: `http://webhook:5000/project/${objectId}/ftp`,
      followRedirects: true
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  }

  var jobs = await startProject(project);

  return jobs;
});

Parse.Cloud.define('jobStarted', async (request) => {
  const objectId = request.params.objectId;

  // Get the job.
  var query = new Parse.Query('Job');
  var job = await query.get(objectId);
  var project = await job.get('project').fetch();

  // Set the job to running.
  await job.save({'status': 'running', 'startedAt': new Date()});

  // Set project status if appropriate.
  if (project.get('progress') != 'running') {
    await project.save({'progress': 'running'});
    sendEmail(project.id, `Analysis started for project ${project.id}`,
      `Alaska has started analysis of project ${project.id}. Please visit the unique URL for more details.`
    );
  }

  return job;
});

Parse.Cloud.define('jobSuccess', async (request) => {
  var objectId = request.params.objectId;
  var runtime = request.params.runtime;

  // Get the job.
  var query = new Parse.Query('Job');
  var job = await query.get(objectId);
  var project = await job.get('project').fetch();

  // If all the project's jobs are done, set status to success.
  var jobs = await project.relation('jobs').query().find();
  var success = true;
  for (var i = 0; i < jobs.length; i++) {
    var otherJob = jobs[i];
    if (otherJob.get('status') != 'success') {
      success = false;
    }
  }
  if (success) {
    project.set('progress', 'success');
    sendEmail(project.id, `Analysis finished for project ${project.id}`,
      `Alaska finished analysis of project ${project.id}. Please visit the unique URL.`
    )
  }

  await project.save({'oldProgress': project.get('oldProgress') + 1});

  // Set status to success.
  job.set('status', 'success');
  job.set('runtime', runtime);
  job.unset('queuePosition');
  job.set('finishedAt', new Date());
  await job.save();

  await updateQueuePositions();

  return job;
});

Parse.Cloud.define('jobError', async (request) => {
  var objectId = request.params.objectId;

  // Get the job.
  var query = new Parse.Query('Job');
  var job = await query.get(objectId);
  var project = await job.get('project').fetch();

  await project.save({'oldProgress': -project.get('oldProgress'), 'progress': 'error'});

  // Set status to error.
  job.set('status', 'error');
  job.unset('queuePosition');
  job.set('finishedAt', new Date());
  await job.save();

  // Remove other queued jobs from the queue.
  var project = job.get('project');
  var relation = project.relation('jobs');
  var queued = await relation.query().equalTo('status', 'queued').find();
  for (var i = 0; i < queued.length; i++) {
    var queued_job = queued[i];
    queued_job.unset('queuePosition');
    await queued_job.save();
  }

  await updateQueuePositions();

  // Send error email.
  sendEmail(project.id, `Error has occured for project ${objectId}`,
    `Alaska encountered an error while running analysis for project ${objectId}.
    Please visit the unique URL for more details.`);

  return job;
});

Parse.Cloud.define('getOutput', async (request) => {
  var objectId = request.params.objectId;

  // Send request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: 'http://webhook:5000/job/' + objectId + '/output',
      followRedirects: true,
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  } else {
    return data.result;
  }
});

Parse.Cloud.define('openSleuth', async (request) => {
  const objectId = request.params.objectId;

  const query = new Parse.Query('Project');
  const project = await query.get(objectId);

  // Check if shiny server is already running.
  if (project.has('shiny')) {
    var shiny = await project.get('shiny').fetch();
    if (shiny.has('port')) {
      return {'port': shiny.get('port'), 'wait': 0};
    }
  }

  // Get available ports.
  var shinyQuery = new Parse.Query('Shiny');
  shinyQuery.select('port');
  var shinies = await shinyQuery.find();
  var ports = [];
  for (var i = 0; i < shinies.length; i++) {
    const s = shinies[i];
    ports.push(s.get('port'));
  }

  // Find random open port between 10000 and 20000.
  var port = Math.floor(Math.random() * 10000) + 10000;
  while (ports.includes(port)) {
    port = Math.floor(Math.random() * 10000) + 10000;
  }

  console.log(port);

  // Send request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: `http://webhook:5000/project/${objectId}/sleuth/${port}`,
      followRedirects: true,
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  } else {
    // Success. Make new row in Shiny table.
    var Shiny = Parse.Object.extend('Shiny');
    var shiny = new Shiny({'port': port, 'project': project, ...data.result});
    await shiny.save();
    await project.save({'shiny': shiny});

    return {'port': port, 'wait': 5000};
  }
});

Parse.Cloud.define('compileProject', async (request) => {
  const objectId = request.params.objectId;

  // Send request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      url: `http://webhook:5000/project/${objectId}/compile`,
      followRedirects: true,
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  }

  return data.result;
});

Parse.Cloud.define('uploadProject', async (request) => {
  const objectId = request.params.objectId;
  const host = request.params.host;
  const username = request.params.username;
  const password = request.params.password;
  const geo_username = request.params.geo_username;

  // Send request to webhook.
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      url: `http://webhook:5000/project/${objectId}/upload`,
      followRedirects: true,
      body: { host, username, password, geo_username }
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  var data = response.data;

  console.log(data);

  if (!('result' in data) ){
    throw data;
  }

  return data.result;
});

Parse.Cloud.define('sendEmail', async (request) => {
  const objectId = request.params.objectId;
  const subject = request.params.subject;
  const message = request.params.message;

  const response = await sendEmail(objectId, subject, message);
  const data = response.data;

  if (!('result' in data)) {
    throw data;
  }
  return data.result;
});


/* Cloud code hooks. */
Parse.Cloud.beforeDelete('Project', async function(request) {
  var project = request.object;

  // Notify webhook that this project is to be deleted.
  var response = await Parse.Cloud.httpRequest({
    method: 'POST',
    url: 'http://webhook:5000/project/' + project.id + '/delete',
    followRedirects: true,
  });
  var data = response.data;

  if (!('result' in data) ){
    throw data;
  }

  // Remove all related jobs.
  var jobs = await project.relation('jobs').query().find();
  for (var i = 0; i < jobs.length; i++) {
    var job = jobs[i];
    job.destroy();
  }

  // Remove all open shiny servers.
  var shiny = project.get('shiny');
  if (shiny != null) {
    shiny.destroy();
  }
});

Parse.Cloud.beforeDelete('Sample', async function(request) {
  var sample = request.object;

  // Remove all related reads.
  var reads = await sample.relation('reads').query().find();
  for (var i = 0; i < reads.length; i++) {
    var read = reads[i];
    read.destroy();
  }
});

Parse.Cloud.beforeDelete('Shiny', async function(request) {
  var shiny = request.object;
  var project = await shiny.get('project').fetch();

  // Send request to webhook to stop container.
  var response = await Parse.Cloud.httpRequest({
    method: 'POST',
    url: `http://webhook:5000/project/${project.id}/sleuth/close`,
    followRedirects: true,
  });
  var data = response.data;

  if (!('result' in data) ){
    throw data;
  }
});


// Starts the project.
// Also call this function to restart an errored project.
// TODO: detect when new analysis has been added and enqueue that too
async function startProject(project) {
  var job_query = project.relation('jobs').query();
  var jobs = await job_query.ascending('analysis.step').find();

  // Find all active analyses in order.
  var analysis_query = new Parse.Query('Analysis');
  analysis_query.equalTo('active', true);
  analysis_query.ascending('step');
  var analyses = await analysis_query.find();

  var Job = Parse.Object.extend('Job');
  for (var i = 0; i < analyses.length; i++) {
    var analysis = analyses[i];

    // Check if existing jobs are successful.
    if (i < jobs.length) {
      var job = jobs[i];

      if (job.get('status') != 'success') {
        await enqueueJob(job);
      }
    } else {
      console.log(i, jobs.length);
      // Add any new, active analyses.
      var job = new Job({'project': project,
                         'analysis': analysis,
                         'commands': []});
      await enqueueJob(job);

      jobs.push(job);

      // Add job to relation.
      project.relation('jobs').add(job);
      await project.save();
      project = await project.fetch();
    }
  }

  // Set last job to archive the entire project.
  var last = jobs[jobs.length - 1];
  last.set('archive', true);
  await last.save();

  // Send error email.
  sendEmail(project.id, `Project ${project.id} has been queued`,
    `Alaska has put analysis of project ${project.id} in the queue.
    Please visit the unique URL for further details.`);

  return jobs;

}

async function enqueueJob(job) {
  job.set('status', 'queued');
  job.set('queuePosition', await getNextQueuePosition());
  job.set('archive', false);
  await job.save();
}

// Gets the next queue position as an integer.
async function getNextQueuePosition() {
  // Find job with highest queue position.
  var query = new Parse.Query('Job');
  query.greaterThanOrEqualTo('queuePosition', 0).descending('queuePosition');
  var last = await query.first();
  if (last != null) {
    return last.get('queuePosition') + 1;
  } else {
    return 0;
  }
}

// Update queue positions.
async function updateQueuePositions() {
  // Find job with highest queue position.
  var query = new Parse.Query('Job');
  query.greaterThanOrEqualTo('queuePosition', 0).ascending('queuePosition');
  var queue = await query.find();

  for (var i = 0; i < queue.length; i++) {
    var job = queue[i];
    job.set('queuePosition', i);
    await job.save();
  }
}

async function sendEmail(objectId, subject, message) {
  try {
    var response = await Parse.Cloud.httpRequest({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      url: `http://webhook:5000/project/${objectId}/email`,
      followRedirects: true,
      body: { subject, message }
    });
  } catch (e) {
    return {'error': 'httprequest error'};
  }
  return response;
}

// Set all compiling projects to success.
// var compilingQuery = new Parse.Query('Project');
// compilingQuery.equalTo('progress', 'compiling');
// compilingQuery.find().then(function (result) {
//   for (var i = 0; i < result.length; i++) {
//     var project = result[i];
//     project.set('progress', 'success');
//   }
// }, function (error) {
//   throw error;
// });
//
// // Set all uploading projects to compiled.
// var uploadingQuery = new Parse.Query('Project');
// uploadingQuery.equalTo('progress', 'uploading');
// uploadingQuery.find().then(function (result) {
//   for (var i = 0; i < result.length; i++) {
//     var project = result[i];
//     project.set('progress', 'compiled');
//   }
// }, function (error) {
//   throw error;
// });

// Parse.Cloud.beforeDelete('Read', async function(request) {
//   console.log('Read beforeDelete');
//   var read = request.object;
//   var path = read.get('path');
//
//   // Notify webhook that this read is to be deleted.
//   var response = await Parse.Cloud.httpRequest({
//     method: 'POST',
//     url: 'http://webhook:5000/read/delete',
//     followRedirects: true,
//     params: {'path': path}
//   });
//   var data = response.data;
//
//   if (!('result' in data) ){
//     throw data;
//   }
// });


/* Initialize new project. */
// Parse.Cloud.define('newProject' async (request) => {
//   var Parse.Object.extend
// })
