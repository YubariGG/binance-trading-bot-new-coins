# Python Modules:
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

class Email():
    def __init__(self, email, password, targets):
        self.__email = email
        self.__password = password
        self.__targets = targets

    def build_msg(self, subject, target_email, body):
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.__email
        message["To"] = target_email
        message.set_content(body , subtype='html')
        return message

    def server_connection(self, message):
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(self.__email, self.__password)
            smtp.send_message(message)

    def send(self, text, subject):
        for target in self.__targets:
            message = self.build_msg(subject, target, text)
            self.server_connection(message)


if __name__ == '__main__':
    email = Email()
    newCoin = "USD"
    email.send("<p>"+newCoin +" has been found by the bot.</p>", "NEW COIN FOUND")