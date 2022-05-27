# -*- coding: utf-8 -*-
"""Comp5349_a2_500215470.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10GrUOyj2xPaUwdJZyicCalnPWkQXQoFC

### Introduction
This notebook demonstrates a few useful methods for loading json file and for handling nested json objects. The example file is `test.json` in assignment 2.
"""



"""### Creat spark"""

from pyspark.sql import SparkSession

spark = SparkSession \
    .builder \
    .appName("COMP5349 A2 500215470") \
    .getOrCreate()

"""### Load Json file as data frame"""

test_data = "s3://edmondfucomp5349a2/test.json"
test_init_df = spark.read.json(test_data)

# The original file will be loaded into a data frame with one row and two columns
test_init_df.show(1)

test_init_df.printSchema()

from pyspark.sql.functions import explode
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql import Window, Row
from pyspark.sql.types import IntegerType, StringType, FloatType
import random

Test_data_df = test_init_df.select(explode("data").alias("data"))

Test_data_df.show(5)

"""1. paragraph"""

Test_data_df = Test_data_df.select(explode("data.paragraphs").alias("paragraph"))
Test_data_df.show(5)

"""2.paragraph+qas"""

Test_data_df = Test_data_df.select(col("paragraph.context").alias("paragraph_context"),explode("paragraph.qas").alias('qas'))
Test_data_df.show(5)

"""3.paragraph+(qas->)qas_question,qas_is_impossible,answer"""

Test_data_df =Test_data_df.select(col("paragraph_context"),
col("qas.question").alias("qas_question"),
col("qas.is_impossible").alias("qas_is_impossible"),explode_outer("qas.answers").alias('answers'),
)
Test_data_df.show(5)

"""4.Paragraph+qas_question+qas_is_impossible+(answer)->answer_start,answer_text"""

Test_data_df = Test_data_df.select(col("paragraph_context"),
  col("qas_question"),
  col("qas_is_impossible"),
  col("answers.answer_start").alias("answer_start"),
  col("answers.text").alias("answer_text"),
)
Test_data_df.show(5)

"""5.select qas_is_impossible == False"""

Test_data_P_df = Test_data_df.where(col("qas_is_impossible") == False)

Test_data_P_df.show(5)

"""Count the number of contracts that contain poss_record for each question"""

pos_contract_N = Test_data_P_df.groupby("paragraph_context").count().withColumnRenamed("count","positive_contract_num")
pos_contract_N.show(5)

"""Convert to RDD"""

Test_RDD = Test_data_P_df.rdd.map(lambda x:(x[0], x[1], x[2], x[3], x[4])).cache()

"""Cut data to the positive samples and Possible negative samples( stride = 2048 window = 4096)"""

def sample_pos(line):
    stride = 2048
    window = 4096
    result = []
    length = len(line[0])
    loop_num = int(length / stride) + 1
    index = 0
    neg_result = []
    for i in range(loop_num):
        c_start = line[3]
        c_end = line[3] + len(line[4])
        if (i *stride>c_end) or (i*stride+window <c_start):
          neg_result.append(Row(source=line[0][i * stride: i * stride + window], qas_question=line[1], answer_start=0, answer_end=0, type_name="possible negative"))  
        elif(i* stride <= c_start < i * stride + window) :
          if i * stride + window > c_end:
           index_end=c_end-i*stride 
           if index_end>=window:
             index_end=window
           result.append(Row(source=line[0][i * stride: i * stride + window], qas_question=line[1], answer_start=line[3] % stride, answer_end=index_end, type_name="positive"))
           index += 1
          else :
           index_end=window
           result.append(Row(source=line[0][i * stride: i * stride + window], qas_question=line[1], answer_start=line[3] % stride, answer_end=index_end, type_name="positive"))
           index += 1
        elif ( i * stride + window>i* stride >= c_start):
          if i * stride + window > c_end:
           index_end=i*stride-c_end
           if index_end>=window:
             index_end=window
           result.append(Row(source=line[0][i * stride: i * stride + window], qas_question=line[1], answer_start=0, answer_end=index_end, type_name="positive"))
           index += 1
          else :
           result.append(Row(source=line[0][i * stride: i * stride + window], qas_question=line[1], answer_start=0, answer_end=window, type_name="positive"))  
           index += 1          
    result.extend(neg_result[:index])
    return result

pos_Sample_rdd= Test_RDD.flatMap(sample_pos)

pos_Sample_rdd.take(5)

"""RDD -> Dataframe"""

pos_Sample_df= spark.createDataFrame(pos_Sample_rdd).cache()

pos_Sample_df.show(5)

"""Count the number of positive samples for each question. (If the start and end of the answer are not 0, it means positive samples)"""

pos_result = pos_Sample_df.select("source","qas_question","answer_start","answer_end")
pos_count = pos_Sample_df.where(col("type_name")=="positive").groupBy("qas_question").count()

pos_result.show(5)

pos_count.show(5)

"""select qas_is_impossible == true"""

Test_data_IM_df = Test_data_df.where(col("qas_is_impossible") == True).join(pos_count,"qas_question")

Test_data_IM_df.show(5)

"""Count the number of Neg samples for each question"""

impos_sample_df = Test_data_IM_df.join(pos_contract_N ,"paragraph_context").cache()

impos_sample_df.show(5)

"""Calculate the number of Impossible negative samples"""

def sample_impos_count(count, positive_contract_count):
  caclunumber= float(count / positive_contract_count)
  result = int(count / positive_contract_count)
  if caclunumber<result:
    result+=1
  return result

"""udf function to label the ne sample"""

cacluN_fc = udf(lambda x,y:sample_impos_count(x,y))

impos_sample_df = impos_sample_df.withColumn("impossible_count",cacluN_fc(col("count"),col("positive_contract_num"))).select("*",round("impossible_count")).withColumnRenamed("round(impossible_count, 0)","impossible_count_result")

impos_sample_df = impos_sample_df.select("paragraph_context","qas_question","qas_is_impossible","answer_start","answer_text","impossible_count_result")

impos_sample_df.show(5)

"""DataFrame->RDD"""

impos_sample_rdd = impos_sample_df.rdd.map(lambda x:(x[0], x[1], x[2], x[3], x[4], x[5]))

"""Cut data tonegative samples( stride = 2048 window = 4096)"""

def sample_impos(line):
  stride = 2048
  window = 4096
  result = []
  source_number = int(line[5])
  context_length = len(line[1])
  if(context_length % stride ==0):
    times = context_length / stride
  else:
    times = int(context_length / stride) + 1
  for i in range(times):
      result.append(Row(source=line[1][i * stride: i * stride + window], question=line[0], answer_start=0, answer_end=0))
  return result[:source_number]

Ne_rdd = impos_sample_rdd.flatMap(sample_impos)

"""RDD->Dataframe"""

Ne_result = spark.createDataFrame(Ne_rdd).cache()

"""Combine Neg,Pos and Pos Neg result"""

F_result = pos_result.union(Ne_result)

"""Change colume name qas_question to qusetion"""

F_result = F_result.withColumnRenamed("qas_question","question")

"""Final result"""

F_result.show()

"""count result"""

F_result.count()

"""Output json"""

F_result.write.json("output_test.json")
