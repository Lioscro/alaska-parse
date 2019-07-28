import os
import sys
import time
import json
import signal
import smtplib
from email.mime.text import MIMEText

ENVIRONMENT = os.getenv('ENVIRONMENT', 'default')

def sigterm_handler(signal, frame):
    print('SIGTERM received', flush=True)

    sys.exit(0)

# Handle SIGTERM gracefully.
signal.signal(signal.SIGTERM, sigterm_handler)

def poll(path='/alaska/data/email', interval=60):
    while True:
        for file in os.listdir(path):
            if not file.endswith('.json'):
                continue

            email_path = os.path.join(path, file)
            try:
                with open(email_path, 'r') as f:
                    print('sending {}'.format(file))
                    data = json.load(f)

                    fr = data['from']
                    to = data['to']
                    subject = data['subject']
                    message = data['message']

                    print(file, fr, to, subject, flush=True)

                    m = MIMEText(message, 'html')
                    m['From'] = fr
                    m['Subject'] = subject

                    if '@' in to and ENVIRONMENT not in ['default', 'local']:
                        with smtplib.SMTP('localhost') as conn:
                            conn.sendmail(fr, to, m.as_string())

                # Email send was successful.
                new_path = os.path.join(path, 'sent', file)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(email_path, new_path)

            except json.JSONDecodeError:
                print('{} is not a valid json'.format(file), flush=True)
            except KeyError:
                print('required key doesn\'t exist in {}'.format(file), flush=True)
            except (smtplib.SMTPConnectError, ConnectionError):
                print('failed to connect to SMTP server', flush=True)
            except Exception as e:
                print(e, flush=True)
                print('unknown error while sending {}'.format(file), flush=True)

        time.sleep(interval)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Email poller.')
    parser.add_argument('path', type=str, default='/alaska/data/email')
    parser.add_argument('-i', type=int, default=60)
    args = parser.parse_args()

    path = args.path
    interval = args.i

    # Create path if it doesn't exist.
    os.makedirs(path, exist_ok=True)

    poll(path, interval)
