# Trending Celebrities using AWS Rekognition

Uses Python's Pyppeteer and Amazon's "Rekognition" software to create a dataset of trending celebrities based on screenshots from popular celebrity news websites.

## How it works

#### The python script and everything required to run it are stored on an AWS EC2 instance. This EC2 instance runs on a cron every 12 hours at 8 am and 8 pm. When the script is activated, it uses pyperteer (a python port of javaScript pupeteer) to go through a list of different celebrity news websites listed in the code. There are currently nine sites but adding or removing sites shouldn't cause any problems. The script then goes throught the sites one by one in a for loop. For each site it takes a full page screenshot of the homepage and saves it locally. The screenshot is then uploaded to the DataPort S3 Bucket. After the upload, the local screenshot needs to be sent to AWS celebrity recognition which is part of AWS rekognition.
 #### Before "celebrity recognition" can be sent the image it needs to be proccessed a bit. The two major limitations of "celebrity recognition" are the max file size of 5 mb and the size of the image itself. Even if an image is within the 5 mb rekognition struggles to return helpful results with large images. To avoid this problem, the screenshot is sliced up into smaller images which are send to AWS rekognition. These slices are deleted once the process is complete.

 #### When the slices are sent to rekognition a lot of data is returned but we only need to grab the list of celebrities in each slice and add them to a list. The duplicates from this list are then removed and we are left with the list of celebrities found on that site. The next step is to add the names into a CSV file in the DataPort S3 Bucket. The CSV file is downloaded from the bucket and the date and time when the screenshot was taken, the name of the site, and the list of celebrities are appended to the file. Afterwards the file is reuploaded to the DataPort bucket, replacing the old CSV, and the local CSV file is deleted. More in depth analysis of each of these steps can be found below.

# Python Script

## Neccesary Imports

I recommend using a virtual enviornemnt to install the necessary libraries. I used anaconda but you can also use [pip](https://pip.pypa.io/en/stable/). This will make installing the requirements on EC2 a bit easier later on. 

Anaconda manager 
Note: the split image library is not avalible for conda instal so you will have to install pip in conda the pip install split image
```bash
conda install -c anaconda boto3
conda install -c mutirri asyncio
conda install -c conda-forge puppeteer
conda install -c conda-forge selenium
pip install split-image
```
pip
```bash
pip install boto3
pip install asyncio
pip install puppeteer
pip install selenium
pip install split-image
```



## Imports
```python
import os
import csv
import boto3
import shutil
import asyncio
import botocore

from PIL import Image
from sys import platform
from pyppeteer import launch
from dotenv import load_dotenv
from time import gmtime, strftime
from split_image import split_image
```

# Using headless chrome to get screenshots of sities
Uses pyppeteer to open chromium and take a screenshot from the given url. The url, loadtime, timeout, operationalChrome, and imageQuality parameters relate to the pyppeteer screenshoting while the other parameters are used to upload to the S3 bucket (which will be explained later).

The full method along with an explanation of how it works are below.
```python
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
```
## How pyppeteer screenshoting works
#### Launch the browser instance
We want headless to be true since we want the screenshoting to happen in the background. The arguments aren't the most important thing but messing with them can cause problems very quickly so I wouldn't touch them unless you need to.
```python
browser = await launch(headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        ],
    serDataDir=tempFilePath
    )
```
#### Create a new browser page
Change the default navigation timeout. This timeout by default is 30 seconds which may not be enough time for some of the heavier sites. Setting the timeout to 0 will make it so it never times out keep in mind timeout is in milliseconds.
```python
    page = await browser.newPage()
    page.setDefaultNavigationTimeout(timeout=int(timeout))
```
Next we want to go to the url and wait for a certain amount of time (in milliseconds) for the page to load
```python
    await page.goto(url)
    await page.waitFor(loadtime)
```
#### Finally we take our screenshot
The path tells it where to save the screenshot to. We want fullPage to be true so we can get an image of the entire page. In order to take a full page screenshot we need the image type to be jpeg (png by default) so we can ajust the quality to decrease file size. Right now I have the imageQuality set to 40 (100 by default) this has had no noticable impact on rekognition's ability to see the image. Then we upload the image to S3 (explained further below) and close the chrome tab.
```python
    await page.screenshot({'path': localFileName, 'fullPage': True, 'type': 'jpeg', 'quality': imageQuality})
    imageToS3(S3BucketPath, localFileName, s3bucketName, region_name, aws_access_key_id, aws_secret_access_key)
    await browser.close()
```
## Uploading Images to the DataPort S3 Bucket
This takes the screenshot from local storage and uploads it to the S3 bucket. The access keys used here are the ones given by DataPort, the bucket is the DataPort bucket and the S3BucketPath is the path to my bucket within DataPort's massive S3.
```python
def imageToS3(S3BucketPath, localFileName, bucket, region_name, aws_access_key_id, aws_secret_access_key, ):
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    S3BucketPath = 'data/1170518/11306/'+S3BucketPath + localFileName

    try:
        client.upload_file(localFileName, bucket, S3BucketPath)
    except botocore.exceptions.ClientError as e:
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            print('key does not exist')
        elif e.response['Error']['Code'] == 403:
            print('Bucket does not exist')
        else:
            raise e
```


# Using AWS Rekognition's celebrity recognition
The following method takes the screenshot cuts it up into slices every 2000 pixels in length and runs it through AWS rekognition. I'll explain these two parts seperately.
```python
def recognize_celebrities_with_split(filename, s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key,
                                     region_name, aws_access_key_id, aws_secret_access_key):
    photo = getS3Image(filename, s3bucketName, region_name, aws_access_key_id, aws_secret_access_key)
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
```
## Chopping up the image
The following code get the photo either locally or from S3 Bucket, finds the height height of the image (in pixels) and divides to by 2000 to get the number of columns we want to break the image into. 
```python
photo = getS3Image(filename, s3bucketName, region_name, aws_access_key_id, aws_secret_access_key)
h = getImageHeight(photo)
columns = h // 2000
```
```python
def getImageHeight(photo):
    im = Image.open(photo)
    width, height = im.size
    return height
```
#### The split_image method takes in the local file name, number of columns you want to split the image into, number of rows to split image into, and whether you want to square and cleanup the images, and the output directory for the new image slices. Depending on the size of the webpage this can return up to 50 image slices or more. For that reason we will delete the local Images folder when we are done.
```python
split_image(photo, columns , 1, should_square=False, should_cleanup=False, output_dir='Images/')
```
## Celebrity recognition
here we use AWS rekogntion to get out list of names.
#### NOTE: DataPorts AWS keys will not work for recogntion which is why you will see the usage of "recog" keys. These keys are mine and to follow along you will need to use your personal AWS keys for this section.
```python
# Creating boto3 session (SEE NOTE)
session = boto3.Session(aws_access_key_id=recog_aws_access_key_id,
                        aws_secret_access_key=recog_aws_secret_access_key, 
                        region_name=region_name)
    # Creating our rekogntion client from our session 
    client = session.client('rekognition')
    # The list where our celeb names will be stored
    celebs = []
    # Opens Image Slices and sends them to rekognition
    for i in range(columns):
        photo = photo.replace('.jpeg', '')
        with open('Images/'+photo + '_' + str(i)+'.jpeg', 'rb') as image:
            try:
                response = client.recognize_celebrities(Image={'Bytes': image.read()})
            except botocore.exceptions.ClientError as e:
                print('Error with AWS rekognition (most likely file size over 5mb)')
                raise e
        # The response from rekognition includes a bunch of other data about 
        # the celebrities in the images but we only want the names.
        for celebrity in response['CelebrityFaces']:
            celebs.append(celebrity['Name'])
    # Deletes the full page screenshot
    os.remove(filename)
    # Deletes the Images folder containing the slices
    shutil.rmtree('Images/')
    # removes duplicate names from celebs list
    celebs = [*set(celebs)]
    return celebs
```

# Appending results to CSV file in S3 bucket
Here we download the CSV file from the DataPort S3 bucket, take the list of celebrities, website names, and filenames and adds them to the end of the CSV, then reupload to S3 and delete the local file.
```python
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
    os.remove('Celebs.csv')
```
First we create our client and check if the CSV exists. If not we will create the CSV in the S3 Bucket.
```python
    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    try:
        client.head_object(Bucket=s3BucketName, Key='data/1170518/11306/Celebs.csv')
    except botocore.exceptions.ClientError as e:
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            client.put_object(Bucket=s3BucketName, Key='Celebs.csv')
```
Next we download the Celebs.csv file from the DataPort S3 Bucket, use csv writer to write the rows from our list of celebrites, reupload to the Bucket, and delete the local file.
```python
    client.download_file(s3BucketName, 'data/1170518/11306/Celebs.csv', 'Celebs.csv')
    print('Appending names to CSV')
    with open(r'Celebs.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        for l in list:
            writer.writerow(l)
    client.upload_file('Celebs.csv', s3BucketName, 'data/1170518/11306/Celebs.csv')
    print('CSV uploaded to S3')
    os.remove('Celebs.csv')
```
# Main method
```python
def main():
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
    
    # 'https://perezhilton.com/' for what ever reason this 
    #  site doesn't work sometimes so I left it out

    # gets enviornment variables from .env further explaination below
    load_dotenv()
    aws_access_key_id=os.environ.get('aws_access_key_id')
    aws_secret_access_key=os.environ.get('aws_secret_access_key')
    region_name=os.environ.get('region_name')
    s3bucketName=os.environ.get('s3bucketName')
    recog_aws_access_key_id=os.environ.get('recognition_aws_access_key_id')
    recog_aws_secret_access_key=os.environ.get('recognition_aws_secret_access_key')
        
    
    #switch to /tmp for aws
    # this should not matter for anything initially I was going to run this script on 
    # AWS lambda and the operational chrome stuff is left over from that
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
```
## Environment Variables
to use enviornment variables the way I have here create a file called .env and add the required variables into it. It should look something like this.
```python
aws_access_key_id='Your access key given by DataPort'
aws_secret_access_key='Your secret access key given by DataPort'
region_name='Your region'
s3bucketName='ieee-dataport'
recognition_aws_access_key_id='Your personal access key (not given by DataPort)'
recognition_aws_secret_access_key='Your peronsal secret access key'
```
you can also put your keys directly in the code but this can create security issues depending on how you use the code.

# Other methods
The remaining methods were made more for organization. They aren't unimportant and are still neccessary for the script to run but they don't do anything to special.
## Downloading images from S3
I realized after making this method that I don't actually need to download any images from S3 and it makes more sense for me to just keep the screenshot file locally and then delete it after its been processed.
#### regardless this function may come in handy for something later so I left it in. For it to work just remove the pass and uncomment the next line.
```python
def getS3Image(localFileName, bucket, region_name, aws_access_key_id, aws_secret_access_key,):
    S3BucketPath = 'data/1170518/11306/Images/' + localFileName

    client = boto3.client('s3', region_name=region_name, aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key)
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
```
## Websites method
prints the names of the celebrities detected in the image and returns the list to be appended to the CSV file
```python
def websites(S3filename, time, url, webname, s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key, 
             region_name, aws_access_key_id, aws_secret_access_key):
    celeb_count = recognize_celebrities_with_split(S3filename, s3bucketName, recog_aws_access_key_id, 
                                                   recog_aws_secret_access_key, region_name, aws_access_key_id, aws_secret_access_key)
    Celeblist = makeCeleblist(celeb_count, time, webname)

    if len(celeb_count):
        print("Celebrities detected: " + ', '.join(celeb_count))
    else:
        print("Celebrities detected: None")
    print()
    return Celeblist
```
## getSiteNames Method
gets the name of the website by removing the clutter in the URL

https://www.TMZ.com -> TMZ
```python
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
```   
## getCelebs Method
runs some important methods and creates some necessary variables
```python
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

        asyncio.get_event_loop().run_until_complete(getScreenShotPy(path, S3filename, sites[url],
                                loadtime, timeout, s3bucketName, region_name, aws_access_key_id, 
                                aws_secret_access_key, operationalChrome, imageQuality))

        BigList.append(websites(S3filename, giventime, sites[url], sitenames[url],
                                s3bucketName, recog_aws_access_key_id, recog_aws_secret_access_key,
                                region_name, aws_access_key_id, aws_secret_access_key))
    return BigList
``` 
# Running on AWS EC2
In order to run a python script on an EC2 instance there are a few relatively simple but very important steps.
#### The first step is to create our requirements.txt. This isn't neccessary for EC2 but it is for other AWS services and makes it so we don't have to install our python libraries manually.
#### With pip use
```Bash
pip freeze > requirements.txt
```
With anaconda use
```Bash
conda list --export > requirements.txt
```
There can be issues with these commands but you want the final output to be formated like this.
```
appdirs==1.4.4
boto3==1.24.28
botocore==1.27.59
brotlipy==0.7.0
```
## Creating an EC2
The next step is making our EC2 instance. There are tons of [guides](https://towardsdatascience.com/how-to-run-your-python-scripts-in-amazon-ec2-instances-demo-8e56e76a6d24) to explain this process that can do it better than I can but I'll go over the important parts.
#
![alt text](https://vegibit.com/wp-content/uploads/2022/09/AWS-application-and-os-images-catalog.png)
#### Go to AWS EC2 and press launch instance. For this project I used an Ubuntu EC2.
#
![alt text](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*oFTm7KYVcAWfbdvB-NDHjQ.png)
You also need a key pair (Type: RSA, File Format: .pem) The name doesn't matter for anything but I would keep it relevent to your project.
## Connecting to Ubuntu EC2
Connecting to the EC2 is simple. Navagite to your EC2 instances and find the one you just created when you click on it you should see an auto-assigned ip address or public ip. Copy the ip and type the command below (I used git Bash for this).
```Bash
ssh -i yourkey.pem ubuntu@11.111.111.11
```
make sure to use your .pem key and given EC2 ip.
## Git cloning into EC2 instance
There are a lot of ways to upload code to an EC2 but for this project I git cloned it in. This makes it easier to continue developing locally. 
#### To do this we first need to install git on the EC2
```python
yum install git -y
```
then just git clone in the repo
```python
git clone git@github.com:<your_git_user_name>/<repo_name>.git
```
now whenever you upload changed to github you can cd into your folder and use these two lines to update your code
```Bash
git fetch
git pull
```
Finally the command to run a python script on an EC2 is
```Bash
python3 handler.py
```
# Setting up a cron
this project is set to run once in the morning and once at night at 8 am and 8 pm. To do this I set up a cron on the EC2.
```Bash
crontab -e
```
and added this line
```Bash
0 8,20 * * * python3 /home/ubuntu/aws-celebritiy-recognition/handler.py
```


## License

idk