import json
import re
import time
from io import BytesIO
from typing import List

from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from PIL import Image

from dingo.data.datasource import S3DataSource
from dingo.io import InputArgs


def try_close(obj):
    """
    Attempt to close the object, ignoring any exceptions that occur.

    Parameters:
    obj: The object to close
    """
    try:
        obj.close()
    except Exception:
        pass


def restore_and_wait(client, bucket: str, key: str, path: str):
    """
    Restore an S3 object and wait for the restoration to complete.

    Parameters:
    client: The S3 client
    bucket: The name of the S3 bucket
    key: The key of the S3 object
    path: The path of the S3 object
    """
    while True:
        head = client.head_object(Bucket=bucket, Key=key)
        restore = head.get("Restore", "")
        if not restore:
            req = {"Days": 1, "GlacierJobParameters": {"Tier": "Standard"}}
            client.restore_object(Bucket=bucket, Key=key, RestoreRequest=req)
            print(f"restoration-started: {path}")
        elif 'ongoing-request="true"' in restore:
            print(f"restoration-ongoing: {path}")
        elif 'ongoing-request="false"' in restore:
            print(f"restoration-complete: {path}")
            break
        time.sleep(3)


def split_s3_path(path: str):
    """
    Split an S3 path into bucket and key.

    Parameters:
    path: The path of the S3 object

    Returns:
    tuple: (bucket, key)
    """
    m = re.compile("^s3a?://([^/]+)(?:/(.*))?$").match(path)
    if m is None:
        return "", ""
    return m.group(1), (m.group(2) or "")


def get_s3_object(client, path: str, **kwargs) -> dict:
    """
    Get an S3 object. If the object is being restored, wait for the restoration to complete.

    Parameters:
    client: The S3 client
    path: The path of the S3 object
    kwargs: Additional parameters

    Returns:
    dict: The object data
    """
    bucket, key = split_s3_path(path)
    try:
        return client.get_object(Bucket=bucket, Key=key, **kwargs)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "GlacierObjectNotRestore":
            restore_and_wait(client, bucket, key, path)
            return client.get_object(Bucket=bucket, Key=key, **kwargs)
        raise RuntimeError("The object cannot be restored.")


def find_s3_image(data: json, input_args: InputArgs) -> List:
    """
    This function retrieves an image from an S3 bucket and returns it as a Python Image object.

    Args: data (json): The JSON data containing the information to locate the image in the S3 bucket. input_args (
    InputArgs): An object containing arguments such as the column_image to traverse the JSON data and S3 bucket details.

    Returns: List: A list containing the Python Image object if the image was successfully retrieved, otherwise an
    empty list.
    """
    res = data
    levels = input_args.column_image.split(".")
    for key in levels:
        res = res[key]
    s3_data_source = S3DataSource(input_args)
    try:
        jpg_s3_obj = get_s3_object(s3_data_source.client, res)
        jpg_s3_stream: StreamingBody = jpg_s3_obj["Body"]
        img = Image.open(BytesIO(jpg_s3_stream.read()))
        try_close(jpg_s3_stream)
    except Exception as e:
        print("get_img error:{}, img_url:{}".format(e, res))
        img = None
    if img is not None:
        return [img]
    return []
