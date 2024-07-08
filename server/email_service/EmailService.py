import os
import traceback
from inspect import currentframe, getframeinfo
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from fastapi import HTTPException
load_dotenv()

class EmailService:
    def __init__(self, sendgrid_key = os.environ.get("SENDGRID_API_KEY")):
        self.client = SendGridAPIClient(sendgrid_key)

    def send_email(self, from_email, to_email, subject, name, email, message_body):
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=f'<strong>Name:</strong> {name}<br><strong>Email:</strong> {email}<br><strong>Message:</strong> {message_body}'
        )
        try:
            response = self.client.send(message)
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

    def notify_error(self, exception):
        to_mail = os.environ.get("TO_EMAIL") if os.environ.get("TO_EMAIL") else "support@drophouse.art"
        message_body = '';
        for exc_head in exception:
            message_body = message_body + f"<strong>{exc_head}:</strong> {exception[exc_head]}<br>";
        
        message = Mail(
            from_email='bucket@drophouse.art',
            to_emails=to_mail,
            subject='ERROR: Drophouse Error',
            html_content=f'{message_body}'
        )
        try:
            response = self.client.send(message)
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

    def notify_imagegen_fail(self, idx, task_id, task_info, progress_time):
        images = task_info['images']
        prompts = task_info['prompts']
        timetaken = task_info["timetaken"]

        message_body = ''
        to_mail = os.environ.get("TO_EMAIL") if os.environ.get("TO_EMAIL") else "support@drophouse.art"
        message_body = message_body + f"<br><strong>Image Generation took:</strong> {timetaken}<br>\
            <strong>Task Id:</strong> {task_id}<br><br>\
            <table style='width:100%; border:solid 1px black; border-collapse: collapse; text-align: center'>\
                <thead>\
                    <tr><th style='border:solid 1px black; border-collapse: collapse;'>AI Model Number</th><th style='border:solid 1px black; border-collapse: collapse;'>Prompt Index</th><th style='border:solid 1px black; border-collapse: collapse;'>Generated Time</th><th style='border:solid 1px black; border-collapse: collapse;'>Prompt</th><th style='border:solid 1px black; border-collapse: collapse;'>Status</th></tr>\
                </thead>\
                <tbody>"
        for i in range(len(prompts)):
            style = "color : black; border:solid 1px black; border-collapse: collapse;"
            if(idx == i):
                style = "color : blue; border:solid 1px black; border-collapse: collapse;"

            message_body = message_body + f"<tr style='{style}'><td style='border:solid 1px black; border-collapse: collapse;'>1</td><td style='border:solid 1px black; border-collapse: collapse;'>{i}</td><td style='border:solid 1px black; border-collapse: collapse;'>{progress_time[i] if i in progress_time else '-- seconds'}</td><td style='border:solid 1px black; border-collapse: collapse;'>{prompts[i]}</td><td style='border:solid 1px black; border-collapse: collapse;'>{'Failed' if isinstance(images[i], Exception) else 'Passed'}</td></tr>"
            message_body = message_body + f"<tr style='{style}'><td style='border:solid 1px black; border-collapse: collapse;'>2</td><td style='border:solid 1px black; border-collapse: collapse;'>{i}</td><td style='border:solid 1px black; border-collapse: collapse;'>{progress_time[i + 3] if (i + 3) in progress_time else '-- seconds'}</td><td style='border:solid 1px black; border-collapse: collapse;'>{prompts[i]}</td><td style='border:solid 1px black; border-collapse: collapse;'>{'Failed' if isinstance(images[i+3], Exception) else 'Passed'}</td></tr>"

        message_body = message_body + f"</tbody></table>"

        message = Mail(
            from_email='bucket@drophouse.art',
            to_emails=to_mail,
            subject='ERROR: Drophouse Error',
            html_content=f'{message_body}'
        )
        try:
            response = self.client.send(message)
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})