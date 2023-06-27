import os
import csv
import boto3
import botocore
import operator
from dotenv import load_dotenv


# def getCSV(region_name, aws_access_key_id, aws_secret_access_key, s3BucketName):
#     client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
#     try:
#         client.head_object(Bucket=s3BucketName, Key='data/1170518/11306/Celebs.csv')
#         client.download_file(s3BucketName, 'data/1170518/11306/Celebs.csv', 'Celebs.csv')
#     except botocore.exceptions.ClientError as e:
#         if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
#             print('file does not exist / not found')


def createCelebDict(region_name, aws_access_key_id, aws_secret_access_key, s3BucketName, topNum):
    # getCSV(region_name, aws_access_key_id, aws_secret_access_key, s3BucketName)
    with open("Celebs.csv", "r", newline='') as source: #, encoding='utf8'
        reader = csv.reader(source)
        with open("output.csv", "w") as result:
            writer = csv.writer(result)
            for r in reader:
                del r[0]
                del r[0]
                writer.writerow(r)

    with open('output.csv', newline='') as file:
        reader = csv.reader(file)
        data = list(reader)
    del data[0]
    CelebDict = {}
    for rows in data:
        for column in range(len(rows)):
            if rows[column] not in CelebDict.keys():
                CelebDict.update({rows[column]: 1})
            elif rows[column] in CelebDict.keys():
                CelebDict[rows[column]] = CelebDict[rows[column]] + 1
    try:
        del CelebDict['']
    except:
        pass
    os.remove('Celebs.csv')
    os.remove('output.csv')
    topNum = len(CelebDict.keys())
    topN = getTopN(CelebDict, topNum)
    
    return topN


def getTopN(CelebDict, n):
    topTenList = []
    topCelebs = {}
    for i in range(n):
        topTenList.append(max(CelebDict.items(), key=operator.itemgetter(1))[0])
        topCelebs.update({max(CelebDict.items(), key=operator.itemgetter(1))[0]:
                           max(CelebDict.items(), key=operator.itemgetter(1))[1]})
        del CelebDict[max(CelebDict.items(), key=operator.itemgetter(1))[0]]

    return(topCelebs)


def createReformatedCSV(topCelebs):
    with open('ReformatedCelebs.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Celebrity", "Mentions"])
        writer.writerows(topCelebs.items())


def reformat(start='Jun_13', end=None, topNum=12):
    load_dotenv()
    aws_access_key_id=os.environ.get('aws_access_key_id')
    aws_secret_access_key=os.environ.get('aws_secret_access_key')
    region_name=os.environ.get('region_name')
    s3bucketName=os.environ.get('s3bucketName')
    topCelebs = createCelebDict(region_name, aws_access_key_id, aws_secret_access_key, s3bucketName, topNum)
    createReformatedCSV(topCelebs)
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    client.upload_file('ReformatedCelebs.csv', s3bucketName, 'data/1170518/11306/ReformatedCelebs.csv')