import csv
import json


with open(
    "dashboard_snapshot.csv",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for i, row in enumerate(reader):

        s = row["metrics_json"]

        try:
            json.loads(s)

        except Exception as e:

            print("错误行:", i)
            print(e)

            pos = getattr(e, "pos", None)

            if pos:
                print("\n错误位置附近:")
                print(s[pos-200:pos+200])

                print("\nrepr:")
                print(repr(s[pos-50:pos+50]))

            break