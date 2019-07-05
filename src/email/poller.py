import os
import sys
import time
import json
import signal
import smtplib
from email.mime.text import MIMEText

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

            with open(os.path.join(path, file), 'r') as f:
                print('sending {}'.format(file))
                try:
                    data = json.load(f)

                    fr = data['from']
                    to = data['to']
                    subject = data['subject']
                    message = data['message']

                    m = MIMEText(message, 'html')
                    m['From'] = fr
                    m['Subject'] = subject

                    with smtplib.SMTP('localhost') as conn:
                        conn.sendmail(fr, to, m.as_string())
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
