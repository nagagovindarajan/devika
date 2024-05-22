import boto3
import json

from src.logger import Logger
from botocore.exceptions import ClientError
from src.config import Config

logger = Logger()
config = Config()

class AWSBedrock:
    def __init__(self):
        aws_profile = config.get_aws_profile()
        self.client = boto3.Session(profile_name=aws_profile).client('bedrock')
        self.runtime_client = boto3.Session(profile_name=aws_profile).client("bedrock-runtime")

    def inference(self, model_id: str, prompt: str) -> str:

        if "claude-3" in model_id:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            })

            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response["body"].read())
            result = response_body["content"][0]["text"]

        else:
            body = json.dumps({
                "prompt":f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": 4096,
                "temperature": 0.5
            })

            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json"
            )
            response_body = json.loads(response["body"].read())
            result = response_body["completion"]

        return result
  
    def list_foundation_models(self):
        """
        List the available Amazon Bedrock foundation models.

        :return: The list of available bedrock foundation models.
        """

        try:
            response = self.client.list_foundation_models()
            models = response["modelSummaries"]
            logger.info(f"Got foundation models. : {models}")
            return models

        except ClientError:
            logger.error("Couldn't list foundation models.")
            raise

    def get_foundation_model(self, model_identifier):
        """
        Get details about an Amazon Bedrock foundation model.

        :return: The foundation model's details.
        """

        try:
            return self.client.get_foundation_model(
                modelIdentifier=model_identifier
            )["modelDetails"]
        except ClientError:
            logger.error(
                f"Couldn't get foundation models details for {model_identifier}"
            )
            raise
