package com.kafka;

import org.apache.kafka.common.Cluster;
import org.apache.kafka.common.utils.Utils;
import org.apache.kafka.clients.producer.Partitioner;

import java.util.Map;

public class DevicePartitioner implements Partitioner {
    @Override
    public int partition(String topic, Object key, byte[] keyBytes, Object value, byte[] valueBytes, Cluster cluster) {
        int numPartitions = cluster.partitionsForTopic(topic).size();
        if (key == null) { return 0; }

        String deviceId = key.toString();

        if (deviceId.equals("0")) { return 0; } 
	else if (deviceId.equals("1")) { return 1 % numPartitions; }

        return Math.abs(Utils.murmur2(keyBytes)) % numPartitions;
    }

    @Override
    public void configure(Map<String, ?> configs) {}

    @Override
    public void close() {}
}
