import ftplib

from utils import welcome, today_timestamps


def upload(channel, shift=0):
    start, _ = today_timestamps(-1)
    print("[+] [%s] upload graph %s" % (channel, start))

    filename = '%s_%s_stats.html' % (channel, start.strftime("%m%d%Y"))
    session = ftplib.FTP('ftp.server', 'xxxxxxxxx', 'xxxxxxxxxx')
    session.cwd('htdocs')
    file = open(filename, 'rb')
    session.storbinary('STOR index.html', file)
    file.close()
    session.quit()

    print("[+] [%s] uploaded" % channel)


def main():
    welcome()
    upload("mystream", shift=-1)


if __name__ == '__main__':
    main()
