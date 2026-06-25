import os

def run_report(filename):
    os.system("cat " + filename)

def delete_file(path):
    os.system("rm -rf " + path)
