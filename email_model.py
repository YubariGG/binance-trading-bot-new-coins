# Python Modules:
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid


class Email():
    def __init__(self):
        self.__email = "idom.consultants@gmail.com"
        self.__password = "bEQmxNMwVhWJS5c--KbSnKcybaU="
        self.__targets = ["jaime.hernandez@idom.com", "iker.camacho@idom.com",
                          "jon.bilbao@idom.com", "jaimernandez.94@gmail.com"]

    def build_msg(self, subject, target_email, body):
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.__email
        message["To"] = target_email
        message.set_content(body, subtype='html')
        return message

    def server_connection(self, message):
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(self.__email, self.__password)
            smtp.send_message(message)

    def send(self, text, subject):
        for target in self.__targets:
            subject = subject
            body = text
            message = self.build_msg(subject, target, body)
            self.server_connection(message)


if __name__ == '__main__':
    email = Email()
    newCoin = "USD"
    email.send("<p>"+newCoin + " has been found by the bot.</p>",
               "NEW COIN FOUND")
