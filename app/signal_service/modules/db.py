import sqlite3

class Database:
    def __init__(self):
        self.con = sqlite3.connect('./db/stress.db')
        self.cur = self.con.cursor()

    def init_tables(self):
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stress_windows (
                patient_id TEXT,
                timestamp TIMESTAMP
            )
            """
        )

        self.con.commit()

    def append_stress_window(self, patient_id: str, timestamp: float):
        print(str, timestamp, type(timestamp))
        self.cur.execute(
            """ INSERT INTO stress_windows VALUES (?, ?) """,
            (patient_id, timestamp) 
        )

        self.con.commit()

    def get_patient_ids(self):
        rows = self.cur.execute(
            """
            SELECT DISTINCT patient_id
            FROM stress_windows
            WHERE patient_id IS NOT NULL
            ORDER BY CAST(patient_id AS INTEGER), patient_id
            """
        ).fetchall()
        return [row[0] for row in rows]

    def get_avg_stress_count_per_day_of_week(self, patient_id: str):
        results = []
        res = self.cur.execute(
            """
            WITH stress_windows_day AS (
                SELECT 
                    patient_id,
                    strftime('%w', timestamp, 'unixepoch') AS day_of_week,
                    COUNT(*) OVER (PARTITION BY patient_id) AS total_windows
                FROM stress_windows
                WHERE patient_id = ?
            )

            SELECT
                patient_id,
                day_of_week,
                total_windows,
                COUNT(*) AS stress_counts,
                (COUNT(*) * 1.0 / total_windows) AS avg_stress_counts
            FROM
                stress_windows_day
            GROUP BY
                patient_id, day_of_week, total_windows
            ORDER BY
                patient_id, day_of_week
            """
        , (patient_id,))

        for row in res.fetchall():
            patient_id, day_of_week, total_window, stress_counts, avg_stress_counts = row
            results.append({
                'patient_id': patient_id,
                'day_of_week': day_of_week,
                'stress_counts': stress_counts,
                'avg_stress_counts': avg_stress_counts,
            })

        return results

    def get_stress_distribution_per_day_of_week(self, patient_id: str):
        results = []
        res = self.cur.execute(
            """
            WITH stress_windows_day AS (
                SELECT 
                    patient_id,
                    strftime('%H', timestamp, 'unixepoch') AS hour_of_day,
                    strftime('%w', timestamp, 'unixepoch') AS day_of_week
                FROM stress_windows
                WHERE patient_id = ?
            )

            SELECT
                patient_id,
                hour_of_day,
                day_of_week,
                (hour_of_day / 3) AS time_region,
                COUNT(*) AS stress_counts
            FROM
                stress_windows_day
            GROUP BY
                patient_id, day_of_week, hour_of_day
            ORDER BY
                patient_id, day_of_week, hour_of_day
            """
        , (patient_id,))

        for row in res.fetchall():
            patient_id, hour_of_day, day_of_week, time_region, stress_counts = row
            results.append({
                'patient_id': patient_id,
                'hour_of_day': hour_of_day,
                'day_of_week': day_of_week,
                'time_region': time_region,
                'stress_counts': stress_counts,
            })

        return results
