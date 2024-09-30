import sys
import jpype
import jaydebeapi
import csv

# Note: change the driver path to the path on your computer
jdbc_url = 'jdbc:postgresql://serpent-gv.cqrs9do6lykf.us-east-1.rds.amazonaws.com:5432/postgres'
jdbc_driver = ('/home/sfitch/.config/JetBrains/DataGrip2024.1/jdbc-drivers/PostgreSQL/42.6.0/org/postgresql/postgresql'
               '/42.6.0/postgresql-42.6.0.jar')
jdbc_user = 'postgres'
jdbc_password = 'iBAZ9tyYm0K-mKreqdGrPv,Ud5NF37'


# Assumes one uuid in given file. Deletes all existing data for this uuid and inserts data from file.
def insert_trajectory(trajectory_path):
    trajectory = []
    with open(trajectory_path, mode='r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            trajectory.append(row)

    # Generate SQL insert statement
    values = []
    uuid = trajectory[0]['device_uuid']  # assumes only one uuid in file
    for entry in trajectory:
        values.append(f"('{entry['device_uuid']}', to_timestamp({entry['time']}), {entry['mcc']}, {entry['mnc']}, {entry['area_code']}, {entry['cell_id']})")
    sql_statement = ("DELETE FROM device_cell_survey WHERE device_uuid = '" + uuid + "';\n"
                     + "INSERT INTO device_cell_survey (device_uuid, time, mcc, mnc, area_code, cell_id) VALUES\n"
                     + ",\n".join(values) + ";")
    try:
        # Create cursor
        cursor = conn.cursor()
        cursor.execute(sql_statement)
    except Exception as e:
        print(f"Error importing data: {str(e)}")
    finally:
        # Close cursor
        if cursor:
            cursor.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 insert.py <trajectory csv file>")
    input_file = sys.argv[1]

    try:
        # Initialize JVM (if not already initialized)
        if not jpype.isJVMStarted():
            jpype.startJVM(jpype.getDefaultJVMPath(), "-Djava.class.path=%s" % jdbc_driver)

        # Establish connection using jaydebeapi
        conn = jaydebeapi.connect('org.postgresql.Driver', jdbc_url, [jdbc_user, jdbc_password], jdbc_driver)

        insert_trajectory(input_file)

    finally:
        # Close connection
        if conn:
            conn.close()

        # Shutdown JVM (if used)
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
