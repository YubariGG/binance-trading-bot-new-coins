# Python imports:
import boto3
import io
import json

# Config variables
with open(f"{os.path.dirname(os.path.realpath(__file__))}/auth.yml") as file:
    auth = yaml.load(file, Loader=yaml.FullLoader)


class Reader:
    def __init__(self):
        self.__BUCKET_NAME = "market-search-storage"
        self.session = boto3.Session(
            aws_access_key_id=auth["aws_key"], aws_secret_access_key=auth["aws_id"])

    def readData(self, object_name):
        s3 = self.session.client('s3')
        object = s3.get_object(Bucket=self.__BUCKET_NAME,
                               Key=object_name)['Body'].read()
        bytes_object = io.BytesIO(object)
        try:
            return json.load(bytes_object)
        except:
            return None

    def writeData(self, json_object, object_name):
        s3 = self.session.resource('s3')
        object = s3.Object(self.__BUCKET_NAME, f"{object_name}")
        result = object.put(Body=json.dumps(json_object))
        response = result.get('ResponseMetadata')

        if response.get('HTTPStatusCode') == 200:
            print(f"Data uploaded successfully: {object_name}")
        else:
            print(f"Data was not uploaded: {object_name}")


if __name__ == '__main__':
    reader = Reader()

    print(reader.readData("all_shares.json").keys())
    print(reader.readData("new_shares.json"))
