import jpype
import jaydebeapi
import pandas as pd

# Note: change the driver path to the path on your computer
jdbc_url = 'jdbc:postgresql://serpent-gv.cqrs9do6lykf.us-east-1.rds.amazonaws.com:5432/postgres'
jdbc_driver = ('/home/sfitch/.config/JetBrains/DataGrip2024.1/jdbc-drivers/PostgreSQL/42.6.0/org/postgresql/postgresql'
               '/42.6.0/postgresql-42.6.0.jar')
jdbc_user = 'postgres'
jdbc_password = 'iBAZ9tyYm0K-mKreqdGrPv,Ud5NF37'

query_all = """
WITH cell_towers AS (
    SELECT
        mcc,
        mnc,
        area_code,
        cell_id,
        ROW_NUMBER() OVER (ORDER BY mcc, mnc, area_code, cell_id) AS cell_index
    FROM
        (SELECT DISTINCT mcc, mnc, area_code, cell_id FROM device_cell_survey) AS distinct_cells
)
SELECT
    d.device_uuid,
    EXTRACT(EPOCH FROM (d.time )) AS time,
    ct.cell_index
FROM
    device_cell_survey d
JOIN
    cell_towers ct ON
    d.mcc = ct.mcc
    AND d.mnc = ct.mnc
    AND d.area_code = ct.area_code
    AND d.cell_id = ct.cell_id
WHERE
    d.device_uuid != '28e5c6af-5e45-4278-a207-c541eaee7bba' -- exclude synthetic device 1
    AND d.device_uuid != '8628622e-851e-42a1-875a-527d4af7f7a8' -- exclude all tower device
    AND d.device_uuid != '4ea0f558-51cb-45e3-94f9-9a0145ab5930' -- exclude synthetic device 2
ORDER BY
    time;
"""


def export_all(conn):
    try:
        # Create cursor
        cursor = conn.cursor()
        # Execute the parameterized query for the given UUID
        cursor.execute(query_all)
        # Fetch all results
        results = cursor.fetchall()
        # Convert results to DataFrame
        df = pd.DataFrame(results, columns=['device_uuid', 'time', 'cell_index'])
        # Export to CSV
        df.to_csv(f"gv-data/trajectories.csv", index=False)
    except Exception as e:
        print(f"Error exporting data: {str(e)}")
    finally:
        # Close cursor
        if cursor:
            cursor.close()


if __name__ == "__main__":
    try:
        # Initialize JVM (if not already initialized)
        if not jpype.isJVMStarted():
            jpype.startJVM(jpype.getDefaultJVMPath(), "-Djava.class.path=%s" % jdbc_driver)

        # Establish connection using jaydebeapi
        conn = jaydebeapi.connect('org.postgresql.Driver', jdbc_url, [jdbc_user, jdbc_password], jdbc_driver)

        export_all(conn)

    finally:
        # Close connection
        if conn:
            conn.close()

        # Shutdown JVM (if used)
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
