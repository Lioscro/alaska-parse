'''
Contains class to send and receive queries to and from Parse Server.
'''
import json
import requests

class ParseQuery:
    '''
    Wrapper around requests module to easily send and receive queries
    to and from Parse Server.
    '''
    def __init__(self, hostname, appId, masterKey=None):
        '''
        Constructor.
        '''
        self.hostname = hostname
        self.appId = appId
        self.masterKey = masterKey

    def _makeUrl(self, endpoint):
        return self.hostname + '/' + endpoint

    def _makeHeaders(self, content_type, use_master):
        headers = {"X-Parse-Application-Id": self.appId,
                   "Content-Type": content_type}
        if use_master:
            headers['X-Parse-Master-Key'] = self.masterKey

        return headers

    def _post(self, endpoint, content_type, data, use_master=True):
        '''
        Sends an HTTP POST request.
        '''
        url = self._makeUrl(endpoint)
        headers = self._makeHeaders(content_type, use_master)

        r = requests.post(url, headers=headers, data=data)

        # TODO check response code

        return r

    def count(self, endpoint, constraints={}, use_master=False):
        '''
        Returns the count of objects for a query.
        '''
        url = self._makeUrl(endpoint)
        headers = self._makeHeaders('application/json', use_master)

        # Apply count constraints.
        constraints['count'] = 1
        constraints['limit'] = 0

        r = requests.get(url, headers=headers, data=json.dumps(constraints))

        return r.json()['count']

    def getObjectWithId(self, endpoint, objectId, constraints={}):
        '''
        Retrieve a single object that matches the objectId.
        '''
        url = self._makeUrl(endpoint + '/' + objectId)
        headers = self._makeHeaders('application/json', False)


        r = requests.get(url, headers=headers, data=json.dumps(constraints))

        return r.json()

    def get(self, endpoint, constraints={}, all=False, use_master=False):
        '''
        Sends an HTTP GET request.
        This is essentially exactly as it sounds.
        Use this function to "GET" some information from the server.

        Arguments:
        endpoint    -- (str) path to the table you want to look up
        constraints -- (dict) of search constraints (i.e. filters)
        All         -- (bool) whether or not to get every object
                              by default, API requests retrieve max 100 objects
        use_master  -- (bool) whether or not to use the master key

        Returns:
        A list of dictionaries of whatever was found.

        Example:
        If you want to get all the Wallpapers that have not been fetched yet:
        ParseQuery.get('classes/Wallpapers', {'where': {'fetched': {'$ne': True}}}, False)

        If you want all urls of Wallpapers:
        ParseQuery.get('classes/Wallpapers', {'keys': 'url'}, False)

        http://docs.parseplatform.org/rest/guide/#queries
        for more info.
        '''
        url = self._makeUrl(endpoint)
        headers = self._makeHeaders('application/json', use_master)
        results = []

        r = requests.get(url, headers=headers, data=json.dumps(constraints))
        results += r.json()['results']

        skip = 0
        while all and r.json()['results']:
            skip += 100
            constraints['skip'] = skip
            r = requests.get(url, headers=headers, data=json.dumps(constraints))
            results += r.json()['results']

        # TODO check response code

        return results

    def getConfig(self):
        '''
        Get Parse Server configurations.
        '''
        url = self._makeUrl('config')
        headers = self._makeHeaders('application/json', False)

        r = requests.get(url, headers=headers)

        return r.json()['params']

    def create(self, endpoint, obj, use_master=False):
        '''
        Create a new row in the Parse Server.
        Don't use this to update an already existing row!

        Arguments:
        endpoint   -- (str) path to the table you want to make the new thing in
        obj        -- (dict) object to add
                             any keys not already in the table will be added
                             without warning
        use_master -- (bool) whether or not to use the master key

        Returns:
        A dictionary that contains the objectId and createdAt of the newly
        created object.

        Example:
        If you want to add a new wallpaper, only knowing the url:
        ParseQuery.create('classes/Wallpapers', {'url': <SOME_URL>}, True)

        http://docs.parseplatform.org/rest/guide/#objects
        '''
        r = self._post(endpoint, 'application/json', json.dumps(obj), use_master)

        return r.json()

    def update(self, endpoint, objectId, obj, use_master=False):
        '''
        Update an existing row in the Parse Server.
        Don't use this to create a new row.

        Arguments:
        endpoint   -- (str) path to the table you want to make the new thing in
        objectId   -- (str) objectId of the object you want to modify
        obj        -- (dict) of fields to update
        use_master -- (bool) whether or not to use the master key

        Returns:
        A dictionary that contains updatedAt of the updated object.

        Example:
        If you want to update the height of a wallpaper:
        ParseQuery.update('classes/Wallpapers', <OBJECT_ID>, {'height': 100}, False)

        http://docs.parseplatform.org/rest/guide/#objects
        '''
        url = self._makeUrl(endpoint + '/' + objectId)
        headers = self._makeHeaders('application/json', use_master)

        r = requests.put(url, headers=headers, data=json.dumps(obj))

        return r.json()

    def delete(self, endpoint, objectId, use_master=False):
        '''
        Delete an existing row in the Parse Server.

        Arguments:
        endpoint   -- (str) path to the table
        objectId   -- (str) objectId of the object you want to delete
        use_master -- (bool) whether or not to use the master key

        Returns: None
        '''
        url = self._makeUrl(endpoint + '/' + objectId)
        headers = self._makeHeaders('application/json', use_master)

        r = requests.delete(url, headers=headers)

    def upload(self, file, fname, content_type, use_master=False):
        '''
        Upload a file to the server.
        Note that if you want to associate a file with a row in the database,
        you must first upload the file, and then update the row so that
        a field points to that file.

        Arguments:
        file         -- (file-like object) file to upload
        fname        -- (str) what the file name should be on the server
        content_type -- (str) MIME type of the file
                              jpeg image: 'image/jpeg'
                              png image: 'image/png'
                              pdf: 'application/pdf'
                              text file: 'text/plain'
        use_master   -- (bool) whether or not to use the master key

        Returns:
        A dictionary that contains the name and url to the uploaded file.

        Example:
        If you want to upload a jpg image:
        with open('<IMAGE.JPG>', 'rb') as f:
            ParseQuery.upload(f, '<IMAGE.JPG>', 'image/jpeg', False)

        If you already have an Image loaded with PIL:
        from io import BytesIO
        byte_io = BytesIO()
        Image.save(byte_io, 'jpeg')
        byte_io.seek(0)
        ParseQuery.upload(byte_io, '<IMAGE.JPG>', 'image/jpeg', False)

        https://docs.parseplatform.org/rest/guide/#files
        '''
        r = self._post('files/' + fname, content_type, file, use_master)

        return r.json()

    def associateFile(self, endpoint, objectId, field, upload, use_master=False):
        '''
        Associate a file uploaded with ParseQuery.upload with a field of an
        object.
        This is essentially a wrapper around ParseServer.update.

        Arguments:
        endpoint   -- (str) path to the table you want to make the new thing in
        objectId   -- (str) objectId of the object you want to modify
        field      -- (str) field of the object to associate the file with
        upload     -- (dict) the dictinary returned by ParseQuery.upload
        use_master -- (bool) whether or not to use the master key

        Returns:
        A dictionary that contains updatedAt of the updated object.
        '''
        obj = {field: {'__type': 'File', **upload}}
        r = self.update(endpoint, objectId, obj, use_master)

        return r

    def _relation(self, endpoint, objectId, field, className, ids, op,
                  use_master=False):
        '''
        Helper function to implement ParseQuery.addRelation and .removeRelation
        '''
        # Generate data to send.
        # The data contain an 'objects' key.
        # This is a list of dictionaries, one for each idsToAdd.
        # Each dictionary contains '__type': 'Pointer', 'className', and
        # 'objectId'.
        objects = []
        for _id in ids:
            objects.append({'__type': 'Pointer',
                            'className': className,
                            'objectId': _id})
        data = {field: {'__op': op,
                        'objects': objects}}

        self.update(endpoint, objectId, data, use_master)

    def addRelation(self, endpoint, objectId, field, className, idsToAdd,
                    use_master=False):
        '''
        Another wrapper around ParseQuery.update() to easily add Relations
        to a row. Relations are 'pointers' to rows in other classes.
        For instance, for each wallpaper, the mapping to their categories would
        be a Relation. Similarly, the mapping of each category to all the
        wallpapers in the category would be a Relation.
        Note that you must know the class name and objectIds you want to link
        to. All of these objectIds must be in one class (Relations can not
        span multiple classes).
        Also note that this function ADDS a relation. To remove a relation, use
        ParseQuery.removeRelation().

        Arguments:
        endpoint   -- (str) path to the table you want to make the new thing in
        objectId   -- (str) objectId of the object you want to modify
        field      -- (str) field of the object to add the relation to
        className  -- (str) class that contains the rows to link
        idsToAdd   -- (list) of objectIds to be added
        relations  -- (list) of dictionaries, each representing one Relation,
                             containing the fields '__type', 'className', and
                             'objectId'.
        use_master -- (bool) whether or not to use the master key

        Returns:
        A dictionary that contains updatedAt of the updated object.

        Example:
        If you want to add a wallpaper to some categories:
        ParseQuery.addRelation('classes/Wallpapers', '<OBJECT_ID>',
                               'categories', 'Categories',
                               ['<CATEGORY_ID1>', '<CATEGORY_ID2',...])

        https://docs.parseplatform.org/rest/guide/#updating-objects
        '''
        self._relation(endpoint, objectId, field, className, idsToAdd,
                       'AddRelation', use_master)

    def removeRelation(self, endpoint, objectId, field, className, idsToRemove,
                       use_master=False):
        '''
        Opposite of ParseQuery.addRelation().
        '''
        self._relation(endpoint, objectId, field, className, idsToRemove,
                       'RemoveRelation', use_master)

    def getRelated(self, endpoint, objectId, field, className):
        '''
        Get a list of objects in a particular relation field.
        '''
        constraints = {'$relatedTo': {'object':{'__type':'Pointer',
                                                'className': className,
                                                'objectId': objectId},
                                      'key': field}}
        return self.get(endpoint, constraints=constraints, all=True)
