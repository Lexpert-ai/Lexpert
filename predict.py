

def predict_text_entity_extraction(
        project = "handy-outpost-297408",
        endpoint_id = "3273624347889106944",
        content = '',
        location: str = "europe-west4",
        api_endpoint: str = "europe-west4-prediction-aiplatform.googleapis.com",

):
    import os
    from google.cloud import aiplatform
    from google.protobuf import json_format
    from google.protobuf.struct_pb2 import Value

    serice_key_file = "/home/nataly/Nataly/GoogleNLP/MyFirstProject-3b39ba94b3a6.json"
    os.environ[
        "GOOGLE_APPLICATION_CREDENTIALS"] = "/home/nataly/Nataly/GoogleNLP/handy-outpost-297408-7de9b5dc7f72.json"
    os.environ["ENDPOINT_ID"] = "3273624347889106944"
    os.environ["PROJECT_ID"] = "165743141683"


    # The AI Platform services require regional API endpoints.
    client_options = {"api_endpoint": api_endpoint}
    client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
    instance_dict = {"content": content}
    instance = json_format.ParseDict(instance_dict, Value())
    instances = [instance]
    parameters_dict = {}
    parameters = json_format.ParseDict(parameters_dict, Value())
    endpoint = client.endpoint_path(
        project=project, location=location, endpoint=endpoint_id
    )
    client.from_service_account_json(serice_key_file)
    response = client.predict(
        endpoint=endpoint, instances=instances, parameters=parameters
    )

    # See gs://google-cloud-aiplatform/schema/predict/prediction/text_extraction.yaml for the format of the predictions.
    predictions = response.predictions
    return predictions

#predict_text_entity_extraction("handy-outpost-297408", "3273624347889106944", 'After transmission of the draft '
                                                                             # 'legislative act to the national parliaments,')

