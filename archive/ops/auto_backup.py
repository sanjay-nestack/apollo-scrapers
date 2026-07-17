import boto3, datetime, os, subprocess, re

now = datetime.datetime.now()
now = now.strftime("%Y-%m-%d %H:%M:%S")

access_key = os.getenv('AWS_ACCESS_KEY', '')
secret_key = os.getenv('AWS_SECRET_KEY', '')

def Backup_imp_tables(crawler_backup_file, crm_backup_file):
    db_host = 'localhost'
    db_user = 'root'
    db1 = 'crawler_db'
    db2 = 'crm'

    crawler_tables = ['junk_emails_data', 'apollo_emails_data', 'email_open_results']
    crm_tables = ['companies']

    # os.makedirs(output_dir, exist_ok=True)

    try:
        # Backup tables from crawler_db
        # crawler_backup_file = os.path.join(output_dir, f'{db1}_tables.sql')
        crawler_cmd = [
            r'E:\xampp\mysql\bin\mysqldump.exe',
            '--host', db_host,
            '--user', db_user,
            '--no-create-db',
            '--result-file', crawler_backup_file,
            db1, *crawler_tables
        ]
        subprocess.run(crawler_cmd, check=True)
        print(f'✅ crawler_db tables backed up: {crawler_backup_file}')

        # Backup tables from crm
        # crm_backup_file = os.path.join(output_dir, f'{db2}_tables.sql')
        crm_cmd = [
            r'E:\xampp\mysql\bin\mysqldump.exe',
            '--host', db_host,
            '--user', db_user,
            '--no-create-db',
            '--result-file', crm_backup_file,
            db2, *crm_tables
        ]
        subprocess.run(crm_cmd, check=True)
        print(f'✅ crm tables backed up: {crm_backup_file}')

    except subprocess.CalledProcessError as e:
        print(f'❌ Error during backup: {e}')


def Backup(backup_file):
    db_host = 'localhost'
    db_user = 'root'
    db1 = 'crawler_db'
    db2 = 'crm'

    exclude = [
        f'{db1}.tracker',
        f'{db1}.industry_emails',
        f'{db1}.campaign_history',
        f'{db1}.industry_ml',
        f'{db1}.industry_data_templates'          # another example
    ]

    mysqldump_cmd = [
        r'E:\xampp\mysql\bin\mysqldump.exe',
        '--host', db_host,
        '--user', db_user,
        '--databases', db1, db2,
    ]

    for table in exclude:
        mysqldump_cmd.extend(['--ignore-table', table])

    mysqldump_cmd.extend(['--result-file', backup_file])

    try:
        subprocess.run(mysqldump_cmd, check=True)
        print(f'Backup successful. Backup file: {backup_file}')
    except subprocess.CalledProcessError as e:
        print(f'Error during backup: {e}')

def Restore():
    db_host = 'localhost'
    db_user = 'root'
    db_name = 'restore_db'
    backup_file = '20240111074346.sql'

    mysql_cmd = [
        'E:\\xampp\\mysql\\bin\\mysql.exe',
        '--host', db_host,
        '--user', db_user,
        db_name,
        '-e', f'SOURCE {backup_file}'
    ]

    try:
        subprocess.run(mysql_cmd, check=True)
        print(f'Restore successful from {backup_file}')
    except subprocess.CalledProcessError as e:
        print(f'Error during restore: {e}')

def UploadToAWS(local_file, bucket_name, s3_file):
    s3 = boto3.client(
        's3',
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key,
        region_name = "ap-south-1"
    )
    try:
        s3.upload_file(local_file, bucket_name, s3_file)
        print("Upload To AWS Successful")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False

def DeleteLocalOldest(folder_path, num_files_to_keep=9):
    # Match files like crawler_20250616183000.sql or 20250616183000.sql
    pattern = re.compile(r'(\w*_)?(\d{14})\.sql$')
    
    files = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and pattern.match(f)
    ]

    if len(files) > num_files_to_keep:
        # Sort files based on timestamp part
        files.sort(key=lambda f: pattern.match(f).group(2))  # sort by timestamp
        files_to_delete = files[:len(files) - num_files_to_keep]

        for file in files_to_delete:
            file_path = os.path.join(folder_path, file)
            try:
                os.remove(file_path)
                print(f'🗑️ Deleted local file: {file}')
            except OSError as e:
                print(f'❌ Error deleting file: {e}')

def DeleteS3Oldest(bucket_name, num_files_to_keep = 9):
    s3 = boto3.client(
        's3',
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key,
        region_name = "ap-south-1"
    )
    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' in response:
        objects = response['Contents']
        if len(objects) > num_files_to_keep:
            objects.sort(key=lambda x: x['LastModified'])
            num_files_to_delete = len(objects) - num_files_to_keep
            for i in range(num_files_to_delete):
                s3.delete_object(Bucket=bucket_name, Key=objects[i]['Key'])
                print(f"Deleted file: {objects[i]['Key']}")

# timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
# crawler_backup_file = f'../db_backup/crawler_{timestamp}.sql'
# crm_backup_file = f'../db_backup/crm_{timestamp}.sql'
# complete_backup_file = f'../db_backup/complete_{timestamp}.sql'

# Backup_imp_tables(crawler_backup_file, crm_backup_file)
# Backup(complete_backup_file)
# UploadToAWS(crawler_backup_file, "nestack-crawler-backup", f"crawler_{timestamp}.sql")
# UploadToAWS(crm_backup_file, "nestack-crawler-backup", f"crm_{timestamp}.sql")
# UploadToAWS(complete_backup_file, "nestack-crawler-backup", f"complete_{timestamp}.sql")
# DeleteLocalOldest("../db_backup/")
# DeleteS3Oldest("nestack-crawler-backup")

