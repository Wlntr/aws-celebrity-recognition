import os
#import sys
import csv
#import time
#import Image
import boto3
import shutil
import logging
import zipfile
import asyncio
import requests
import mimetypes
#import importlib
#chrome = importlib.import_module('@sparticuz/chrome-aws-lambda')
#import subprocess
# Webdriver not used
from sys import platform
from pyppeteer import launch
from PIL import Image
from selenium import webdriver
from time import gmtime, strftime
from split_image import split_image
from botocore.exceptions import NoCredentialsError
#from webdriver_manager.chrome import ChromeDriverManager
#from selenium.webdriver.chrome.options import Options

# UNUSED METHODS
# METHOD NOT IN USE (runs on selenium and is not headless)
# Takes in the name of the png and takes of picture of the selected chrome page
def getScreenShot(S3BucketPath, localFileName, url, loadtime, s3bucketName):
    options = webdriver.ChromeOptions()
    options.binary_location = "tmp/headless-chromium"
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--single-process")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--homedir=/tmp")
    
    chromedriver = webdriver.Chrome("tmp/chrome-win/chrome.exe", chrome_options=options)
    chromedriver.get(url)
    chromedriver.save_screenshot(localFileName)
    imageToS3(S3BucketPath, localFileName, s3bucketName)
    chromedriver.quit()
    print('Screenshot taken of: ' + url)
    print('Sc name:', S3BucketPath + localFileName)

    
def recognize_celebrities(filename, s3bucketName, aws_access_key_id, aws_secret_access_key, region_name):
    photo = getS3Image(filename, s3bucketName)
    #columns = 10
    #split_image(photo, columns , 1, should_square=False, should_cleanup=True, output_dir='Images/')
    #for i in range(columns):
    session = boto3.Session(aws_access_key_id=aws_access_key_id,
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)
    client = session.client('rekognition')
    celebs = []

    with open(photo, 'rb') as image:
    #with open(photo  + '_' + str(i), 'rb') as image:
        response = client.recognize_celebrities(Image={'Bytes': image.read()})
    for celebrity in response['CelebrityFaces']:
        celebs.append(celebrity['Name'])
    #os.remove(filename)
    return celebs

# gets chromium zip file from s3 bucket, unzips and extracts all to create an executable chromium file
# not actually headless chromium anymore just normal chromium that will run headless
def headlessChromiumDownload(bucket="celeb-site-screenshots", tempFilePath = 'tmp'):
    zipFilePath = tempFilePath + '/chrome.zip'
    #zipFilePath = '/opt/aws-chrome-lambda.zip'
    s3_bucket = boto3.resource("s3", aws_access_key_id='Your Key Here', aws_secret_access_key='Your Key Here').Bucket(bucket)
    if not os.path.exists(zipFilePath):
        print('installing chromium from s3')
        s3_bucket.download_file("headless-chromium.zip", zipFilePath) # downloads zip file to tmp/chrome.zip
        print('installing zip file')
        with zipfile.ZipFile(zipFilePath, "r") as zip_ref:
            print('extracting from zip file')
            zip_ref.extractall(tempFilePath) # extracts all from zip file to tmp
    else:
        print('chromium already installed')
    print('install complete')
    print()


def chromiumDownloadNoZip(bucket="celeb-site-screenshots", tempFilePath = 'tmp', operationalChrome = 'chrome-win'):
    if not os.path.exists(tempFilePath + '/' + operationalChrome):
        print('running NoZip')
        s3_bucket = boto3.resource("s3", aws_access_key_id='Your Key Here', aws_secret_access_key='Your Key Here').Bucket(bucket)
        for obj in s3_bucket.objects.filter(Prefix = operationalChrome):
            if not os.path.exists(os.path.dirname(tempFilePath+'/'+obj.key)):
                os.makedirs(os.path.dirname(tempFilePath+'/'+obj.key))
            s3_bucket.download_file(obj.key, tempFilePath+'/'+obj.key) # save to same path
        print('install complete')
        print()
    else:
        print('chrome installed')

def crop(infile,height,width):
    im = Image.open(infile)
    imgwidth, imgheight = im.size
    for i in range(imgheight//height):
        for j in range(imgwidth//width):
            box = (j*width, i*height, (j+1)*width, (i+1)*height)
            yield im.crop(box)
    print('l')

def cropImage(infile, height, width, start_num):
    for k,piece in enumerate(crop(infile,height,width),start_num):
        print('o')
        img=Image.new('RGB', (height,width), 255)
        img.paste(piece)
        path=os.path.join('/tmp',"IMG-%s.png" % k)
        img.save(path)
    print('done')

def PNGtoJPG():
    im1 = Image.open(r'TMZ_Jun_06_2023_18H_33M_38S.png')
    im1.save(r'TMZ_Jun_06_2023_18H_33M_38S.jpg')

# deletes chromium to avoid lambda file size problems (I don't know if this is actually needed)
def deleteChromium(tempFilePath):
    if os.path.exists(tempFilePath +'/chrome.zip'):
        os.remove(tempFilePath + '/chrome.zip')
    if os.path.exists(tempFilePath + '/chrome-win'):
        shutil.rmtree(tempFilePath + '/chrome-win')
    if os.path.exists(tempFilePath + '/chrome-linux'):
        shutil.rmtree(tempFilePath + '/chrome-linux')
    print('Chromium deleted')

def imageToS3NoLocal(buffer, S3BucketPath, localFileName, bucket='celeb-site-screenshots'):
    client = boto3.client('s3', region_name='us-east-1', aws_access_key_id='Your Key Here', aws_secret_access_key='Your Key Here')
    #with open(buffer, "rb") as image:
    #    f = image.read()
    #    b = bytearray(f)
    try:
        imageResponse = requests.get(buffer, stream=True).raw
        content_type = imageResponse.headers['content-type']
        extension = mimetypes.guess_extension(content_type)
        client.upload_fileobj(imageResponse, bucket, S3BucketPath)
        print("Upload Successful")

    except FileNotFoundError:
        print("The file was not found")

    except NoCredentialsError:
        print("Credentials not available")