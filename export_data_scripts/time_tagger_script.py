import struct
import pandas as pd
import os

file_path = "<FILE-PATH>"

def read_time_tagger_bin(file_path, chunk_size=100000):
    record_size = 17  # 1 byte per channel, 8 bytes per micro_time (f64), 8 bytes per macro_time (f64)
    
    def record_generator(file_path, record_size):
        with open(file_path, 'rb') as f:
            # Skip header (4 bytes)
            f.read(4)
            while True:
                record = f.read(record_size)
                if len(record) < record_size:
                    break
                yield struct.unpack('<Bdd', record)
    
    records = []
    for i, record in enumerate(record_generator(file_path, record_size)):
        channel, micro_time, macro_time = record
        records.append((f"ch{channel + 1}", round(micro_time, 1), round(macro_time, 1)))

        if (i + 1) % chunk_size == 0:
            yield pd.DataFrame(records, columns=['Event', 'Micro Time (ns)', 'Macro Time (ns)'])
            records = []

    if records:
        yield pd.DataFrame(records, columns=['Event', 'Micro Time (ns)', 'Macro Time (ns)'])


base_dir = os.path.dirname(file_path)
base_name = os.path.basename(file_path).replace('.bin', '.csv')
csv_file = os.path.join(base_dir, base_name)

header_written = False
for df_chunk in read_time_tagger_bin(file_path):
    print(df_chunk) 
    df_chunk.to_csv(csv_file, mode='a', header=not header_written, index=False)
    header_written = True  
