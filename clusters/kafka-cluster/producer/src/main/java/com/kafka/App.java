package com.kafka;

import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.Serializer;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.concurrent.TimeUnit;
import java.util.Properties;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import java.io.InputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

import com.kafka.DevicePartitioner;

class IOTDevice extends Thread {
    String path;
    String eda;
    String ibi;
    String id;

    public IOTDevice (String id, String path) {
	this.id = id;
	this.path = path;
	this.eda = path.concat("/EDA.csv");
	this.ibi = path.concat("/IBI.csv");
    }

    @Override
    public void run() {
	try {
	    ArrayList<Double> eda= readEDA(this.eda);
	    ArrayList<Double> ibi = readIBI(this.ibi);
	    ObjectMapper mapper = new ObjectMapper();

	    Properties props = new Properties();
	    props.put("bootstrap.servers", "localhost:19092");
	    props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
	    props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
	    props.put(ProducerConfig.PARTITIONER_CLASS_CONFIG, DevicePartitioner.class.getName());

	    double initialTime = eda.get(0);
	    int freq = (int) ((double) eda.get(1));
	    List<Double> eda_data = eda.subList(2, eda.size());

	    try (Producer<String, String> producer = new KafkaProducer<>(props)) {
		try {
		    int j = 0;

		    for (int i = 0; i < eda_data.size(); i += freq) {
			int end = i + freq >= eda_data.size() ? eda_data.size() - 1 : i + freq;
			List<Double> edaSample = eda_data.subList(i, end);
			List<Double> ibiSample = new ArrayList<>();
			double curTime = (i / freq) + initialTime;

			while (curTime > ibi.get(j)) {
			    ibiSample.add(ibi.get(j));
			    j++;
			}

			Map<String, Object> jsonBody = new HashMap<>();
			jsonBody.put("timestamp", curTime);
			jsonBody.put("eda", edaSample);
			jsonBody.put("ibi", ibiSample);

			String jsonBodyStr = mapper.writeValueAsString(jsonBody);
			System.out.println(jsonBodyStr);

			try {
			    producer.send(new ProducerRecord<>("signal", this.id, jsonBodyStr)).get();
			} catch(Exception e) {
			    e.printStackTrace();
			}

			TimeUnit.SECONDS.sleep(1); 
		    }
		} 

		catch (Exception e) {
		    e.printStackTrace();
		}
	    }
	}

	catch (Exception e) {
	    e.printStackTrace();
	}
    }

    ArrayList<Double> readEDA(String path) throws Exception {
	ClassLoader classLoader = App.class.getClassLoader();
	ArrayList<Double> eda = new ArrayList<>();

	try (InputStream inputStream = classLoader.getResourceAsStream(path)) {
            if (inputStream == null) {
                throw new IllegalArgumentException("File not found in resources!");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
		String line;
                while ((line = reader.readLine()) != null) {
		    eda.add(Double.parseDouble(line));
                }
            }
        }

	return eda;
    }

    ArrayList<Double> readIBI(String path) throws Exception {
	ClassLoader classLoader = App.class.getClassLoader();
	ArrayList<Double> ibi = new ArrayList<>();

	try (InputStream inputStream = classLoader.getResourceAsStream(path)) {
            if (inputStream == null) {
                throw new IllegalArgumentException("File not found in resources!");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
		String line;
		String header = reader.readLine();
		double startTime = Double.parseDouble(header.split(",")[0]);

                while ((line = reader.readLine()) != null) {
		    double offset = Double.parseDouble(line.split(",")[0]);
		    ibi.add(startTime + offset);
                }
            }
        }

	return ibi;
    }
}


public class App {
    public static void main(String[] args) throws Exception {
	String path_1 = "ADARP/Sensor Data/Part 102C/A01b41_190610-003946";
	String path_2 = "ADARP/Sensor Data/Part 104C/A01d53_190718-193707";

	Thread t1 = new IOTDevice("0", path_1);
	Thread t2 = new IOTDevice("1", path_2);

	t1.start();
	t2.start();
    }
}
