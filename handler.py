import os
import csv
import boto3
import shutil
import asyncio
import botocore
import reformatCSV

from PIL import Image
from sys import platform
from pyppeteer import launch
from dotenv import load_dotenv
from time import gmtime, strftime
from split_image import split_image


# CELEBRITY PROJECT
# Runs a few times a day and takes of picture of a popular media website
# the picture is then processed and the names of the popular celebrities
# in the image are added to a csv file along with the Date and Time
# of when the screenshot was taken

# AWS
# project is currently geared to run on AWS EC2 and send
# images and completed csv file to an s3 bucket
# this means it can still run locally with task scheduleer
# but it doesn't make as much sense

# CRON
# sudo service crond start
# crontab -e
# 0 12 * * * python3 handler.py
# 0 8, 20 * * * python3 handler.py every 12 hours at 8 am


# uses pypputeer to open chromium in background to get screenshots faster than getScreenShot()
async def getScreenShotPy(S3BucketPath, localFileName, url, loadtime, timeout, s3bucketName, region_name, aws_access_key_id,
                          aws_secret_access_key, operationalChrome = 'chrome-win', imageQuality=100,):
    if 'lin' in operationalChrome:
        executable = 'chrome'
        tempFilePath = '/tmp'
    elif 'win' in operationalChrome:
        executable = 'chrome.exe'
        tempFilePath = 'tmp'

    browser = await launch(headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        ],
    serDataDir=tempFilePath
    )
    page = await browser.newPage()
    page.setDefaultNavigationTimeout(timeout=int(timeout))
    await page.goto(url)
    await page.waitFor(loadtime)
    await page.screenshot({'path': localFileName, 'fullPage': True, 'type': 'jpeg', 'quality': imageQuality})
    imageToS3(S3BucketPath, localFileName, s3bucketName, region_name, aws_access_key_id, aws_secret_access_key)
    await browser.close()
    print('Screenshot taken of: ' + url)
    print('Sc name:', S3BucketPath + localFileName)


# uploads image to S3 bucket and deletes local file
def imageToS3(S3BucketPath, localFileName,bucket, region_name, aws_access_key_id, aws_secret_access_key, ):
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    S3BucketPath = 'data/1170518/11306/'+S3BucketPath + localFileName
    print(S3BucketPath)
    try:
        client.upload_file(localFileName, bucket, S3BucketPath)
    except botocore.exceptions.ClientError as e:
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            print('key does not exist')
        elif e.response['Error']['Code'] == 403:
            print('Bucket does not exist')
        else:
            raise e
    

# downloads image from S3 bucket for analysis
def getS3Image(localFileName, bucket, region_name, aws_access_key_id, aws_secret_access_key,):
    S3BucketPath = 'data/1170518/11306/Images/' + localFileName
    print(S3BucketPath)
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    try:
        pass
        #client.download_file(bucket, S3BucketPath, localFileName)
    except botocore.exceptions.ClientError as e:
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            print('key (file) does not exist')
        elif e.response['Error']['Code'] == 403:
            print('Bucket does not exist')
        else:
            raise e
        
    return localFileName


# Uses AWS Rekognition tool to return a list of celebrities in the image
def recognize_celebrities_with_split(filename, s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key,
                                     region_name, aws_access_key_id, aws_secret_access_key):
    photo = filename
    h = getImageHeight(photo)
    columns = h // 2000
    split_image(photo, columns , 1, should_square=False, should_cleanup=False, output_dir='Images/')
    session = boto3.Session(aws_access_key_id=recog_aws_access_key_id,
                            aws_secret_access_key=recog_aws_secret_access_key, 
                            region_name=region_name)
    client = session.client('rekognition')
    celebs = []
    for i in range(columns):
        photo = photo.replace('.jpeg', '')
        with open('Images/'+photo + '_' + str(i)+'.jpeg', 'rb') as image:
            try:
                response = client.recognize_celebrities(Image={'Bytes': image.read()})
            except botocore.exceptions.ClientError as e:
                print('Error with AWS rekognition (most likely file size over 5mb)')
                raise e
        for celebrity in response['CelebrityFaces']:
            celebs.append(celebrity['Name'])
    os.remove(filename)
    shutil.rmtree('Images/')
    celebs = [*set(celebs)]
    return celebs


def getImageHeight(photo):
    im = Image.open(photo)
    width, height = im.size
    return height


# Adds the Date and time to the front of the list
def makeCeleblist(ccc, time, webname):
    Celeblist = []
    Celeblist.append(time)
    Celeblist.append(webname)
    for c in ccc:
        Celeblist.append(c)
    return Celeblist


# Gets CSV file from S3 bucket, appends the list of names to the end of the csv file and reuploads to bucket
def addalltofile(list, region_name, aws_access_key_id, aws_secret_access_key, s3BucketName):
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    try:
        client.head_object(Bucket=s3BucketName, Key='data/1170518/11306/Celebs.csv')
    except botocore.exceptions.ClientError as e:
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            client.put_object(Bucket=s3BucketName, Key='Celebs.csv')

    client.download_file(s3BucketName, 'data/1170518/11306/Celebs.csv', 'Celebs.csv')
    print('Appending names to CSV')
    with open(r'Celebs.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        for l in list:
            writer.writerow(l)
    client.upload_file('Celebs.csv', s3BucketName, 'data/1170518/11306/Celebs.csv')
    print('CSV uploaded to S3')
    reformatCSV.reformat()


# prints the names of the celebrities detected in the image and returns the list to be appended to the CSV file
def websites(S3filename, time, url, webname, s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key,
             region_name, aws_access_key_id, aws_secret_access_key):
    celeb_count = recognize_celebrities_with_split(S3filename, s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key, 
                                                   region_name, aws_access_key_id, aws_secret_access_key)
    Celeblist = makeCeleblist(celeb_count, time, webname)

    if len(celeb_count):
        print("Celebrities detected: " + ', '.join(celeb_count))
    else:
        print("Celebrities detected: None")
    print()
    return Celeblist


# takes urls and returns the name of the site in all caps
def getSiteNames(sites):
    sitenames = []
    for i in range(len(sites)):
        s = sites[i]
        s = s.replace('https://', '')
        if 'www.' in s:
            s = s.replace('www.', '')
        split = s.split('.')
        s = split[0].upper()
        sitenames.append(s)
    return sitenames

       
def getCelebs(sites, giventime, loadtime, sitenames, timeout, 
              s3bucketName, aws_access_key_id, aws_secret_access_key, region_name, operationalChrome, jpeg, imageQuality,
              recog_aws_access_key_id, recog_aws_secret_access_key):
    BigList = []
    if jpeg:
        ending = '.jpeg'
    elif not jpeg:
        ending = '.png'

    for url in range(len(sites)):
        path = 'Images/'
        name = sitenames[url] +'_' + giventime + ending
        S3filename = name

        asyncio.get_event_loop().run_until_complete(getScreenShotPy(path, S3filename, sites[url], loadtime,
                                                                        timeout, s3bucketName, region_name, aws_access_key_id,
                                                                        aws_secret_access_key, operationalChrome, imageQuality))
        
        BigList.append(websites(S3filename, giventime, sites[url], sitenames[url],
                                s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key, region_name, aws_access_key_id, aws_secret_access_key))
    return BigList


# these numbers currently mean nothing
def main(event = 6, context = 4):
    # if jpeg = False image will be png
    jpeg = True
    # Image quality for jpeg only use if jpeg = True
    imageQuality = 40
    # date and time when picture was taken (time since epoch)
    giventime = strftime("%b_%d_%Y_%HH_%MM_%SS", gmtime())
    # time to allow the web page to load in milliseconds
    loadtime = 5000
    # chromium timeout (set to 0 for no timeout)
    timeout = 0
    # list of websites, feel free to add or remove
    sites = ['https://www.tmz.com/', 
             'https://www.eonline.com/',
             'https://people.com/', 'https://pagesix.com/',
             'https://www.usmagazine.com/',
             'https://dlisted.com/', 'https://www.popsugar.com/celebrity/',
             'https://ohnotheydidnt.livejournal.com/', 'https://variety.com/']
    
    #'https://perezhilton.com/'

    load_dotenv()
    aws_access_key_id=os.environ.get('aws_access_key_id')
    aws_secret_access_key=os.environ.get('aws_secret_access_key')
    region_name=os.environ.get('region_name')
    s3bucketName=os.environ.get('s3bucketName')
    recog_aws_access_key_id=os.environ.get('recognition_aws_access_key_id')
    recog_aws_secret_access_key=os.environ.get('recognition_aws_secret_access_key')
        
    #switch to /tmp for aws
    if 'lin' in platform:
        tempFilePath = '/tmp'
        operationalChrome = 'chrome-linux'
    elif 'win' in platform:
        tempFilePath = 'tmp'
        operationalChrome = 'chrome-win'

    sitenames = getSiteNames(sites)
    BigList = getCelebs(sites, giventime, loadtime, sitenames, timeout, s3bucketName, aws_access_key_id, 
                        aws_secret_access_key, region_name, operationalChrome, jpeg, imageQuality,
                        recog_aws_access_key_id, recog_aws_secret_access_key)
    addalltofile(BigList, region_name, aws_access_key_id, aws_secret_access_key, s3bucketName)


if __name__ == "__main__":
    main()
    