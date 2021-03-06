# ffnc-f3aa.tsv

import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from csv import reader
from pyspark import SparkContext
from pyspark.ml.feature import QuantileDiscretizer
from pyspark.sql.functions import isnan

sc = SparkContext("local", "cleaner")
spark = SparkSession.builder.master("local").appName("cleaner").config("spark.some.config.option", "some-value").getOrCreate()

filename = sys.argv[1].split(".")[0].split("/")[3]
data = sc.textFile(sys.argv[1], 1)
data = data.mapPartitions(lambda row: reader(row, delimiter = "\t"))
header = data.first()
data = data.filter(lambda row: row != header)

data = spark.createDataFrame(data, header)

numerical = []
categorical = []
rows = data.count()

for colname in header:
    # If this col has limited unique vals, we consider it as categorical
    if data.filter((data[colname] == "") | (data[colname] == " ") | (data[colname] == "NaN") | (data[colname] == "Unspecified") | isnan(data[colname])).count() > rows * 0.5:
        data = data.drop(colname)
    # If this col has limited unique vals, we consider it as categorical
    elif data.select(colname).distinct().count() < thres:
        categorical.append(colname)
    else:
        # Cast float strs to float, if success, consider it as numerical
        data = data.withColumn(colname, data[colname].cast('float'))
        # Very stupid way to check casting result, should be replaced
        # The reason of doing this is because casting strs like "B" to float won't raise exception but return None instead
        is_numerical = True
        for i in range(5):
            if data.head(5)[i][colname] == None:
                is_numerical = False
                break
        if is_numerical:
            numerical.append(colname)
        else:
            data = data.drop(colname)

if len(numerical) >= (len(numerical) + len(categorical)) * 0.75:
    if (len(numerical) > 0):
        data = data.select(numerical)
        #data = data.withColumn("appended_index", monotonically_increasing_id())
        data.write.format("com.databricks.spark.csv").option("delimiter", "\t").save("num-" + filename + ".out", header = "True")

else:
    # Ignore data set that contains less them 4 valid columns
    # Bin numerical columns and print
    if len(numerical) + len(categorical) > 3:
        for num_col in numerical:
            data = QuantileDiscretizer(numBuckets = 10, inputCol = num_col, outputCol = num_col + "_binned").fit(data).transform(data)
            data = data.drop(num_col)
            data = data.withColumn("appended_index", monotonically_increasing_id())
            data.write.format("com.databricks.spark.csv").option("delimiter", "\t").save("cat-" + filename + ".out",header = "true")
