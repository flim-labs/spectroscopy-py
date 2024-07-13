import os
import shutil

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from components.messages_utilities import MessagesUtilities

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path, ".."))


class ScriptFileUtils:
    @classmethod
    def export_script_file(cls, bin_file_path, file_extension, content_modifier):
        file_name, _ = QFileDialog.getSaveFileName(
            None, "Save File", "", f"All Files (*.{file_extension})"
        )
        if not file_name:
            return
        try:
            bin_file_name = os.path.join(
                os.path.dirname(file_name),
                f"{os.path.splitext(os.path.basename(file_name))[0]}.bin",
            ).replace("\\", "/")

            shutil.copy(bin_file_path, bin_file_name) if bin_file_path else None

            # write script file
            content = content_modifier["source_file"]
            new_content = cls.manipulate_file_content(content, bin_file_name)
            cls.write_file(file_name, new_content)

            # write requirements file only for python export
            if len(content_modifier["requirements"]) > 0:
                requirement_path, requirements_content = cls.create_requirements_file(
                    file_name, content_modifier["requirements"]
                )
                cls.write_file(requirement_path, requirements_content)

            cls.show_success_message(file_name)
        except Exception as e:
            cls.show_error_message(str(e))

    @classmethod
    def write_file(cls, file_name, content):
        with open(file_name, "w") as file:
            file.writelines(content)

    @classmethod
    def create_requirements_file(cls, script_file_name, requirements):
        directory = os.path.dirname(script_file_name)
        requirements_path = os.path.join(directory, "requirements.txt")
        requirements_content = []

        for requirement in requirements:
            requirements_content.append(f"{requirement}\n")
        return [requirements_path, requirements_content]

    @classmethod
    def read_file_content(cls, file_path):
        with open(file_path, "r") as file:
            return file.readlines()

    @classmethod
    def manipulate_file_content(cls, content, file_name):
        return content.replace("<FILE-PATH>", file_name.replace("\\", "/"))

    @classmethod
    def show_success_message(cls, file_name):
        info_title, info_msg = MessagesUtilities.info_handler(
            "SavedScriptFile", file_name
        )
        BoxMessage.setup(
            info_title,
            info_msg,
            QMessageBox.Icon.Information,
            GUIStyles.set_msg_box_style(),
        )

    @classmethod
    def show_error_message(cls, error_message):
        error_title, error_msg = MessagesUtilities.error_handler(
            "ErrorSavingScriptFile", error_message
        )
        BoxMessage.setup(
            error_title,
            error_msg,
            QMessageBox.Icon.Critical,
            GUIStyles.set_msg_box_style(),
        )


class PythonScriptUtils(ScriptFileUtils):

    @staticmethod
    def download_spectroscopy(window, bin_file_path):
        content_modifier = {
            "source_file": """import os
import struct
import matplotlib.pyplot as plt
import numpy as np
file_path = "<FILE-PATH>"
with open(file_path, 'rb') as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)

    # read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))

    
    # ENABLED CHANNELS
    if "channels" in metadata and metadata["channels"] is not None:
        print(
            "Enabled channels: "
            + (
                ", ".join(
                    ["Channel " + str(ch + 1) for ch in metadata["channels"]]
                )
            )
        )   
    # BIN WIDTH (us)    
    if "bin_width_micros" in metadata and metadata["bin_width_micros"] is not None:
        print("Bin width: " + str(metadata["bin_width_micros"]) + "us")    
    # ACQUISITION TIME (duration of the acquisition)
    if "acquisition_time_millis" in metadata and metadata["acquisition_time_millis"] is not None:
        print("Acquisition time: " + str(metadata["acquisition_time_millis"] / 1000) + "s")
    # LASER PERIOD (ns)
    if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None:
        print("Laser period: " + str(metadata["laser_period_ns"]) + "ns") 
    # TAU (ns)
    if "tau_ns" in metadata and metadata["tau_ns"] is not None:
        print("Tau: " + str(metadata["tau_ns"]) + "ns")   
        
              
    channel_curves = [[] for _ in range(len(metadata["channels"]))]
    times = []
    number_of_channels = len(metadata["channels"])
    channel_values_unpack_string = 'I' * 256 
    
    while True:        
        data = f.read(8)
        if not data:
            break
        (time,) = struct.unpack('d', data)    
        for i in range(number_of_channels):
            data = f.read(4 * 256)  
            if len(data) < 4 * 256:
                break
            curve = struct.unpack(channel_values_unpack_string, data)    
            channel_curves[i].append(np.array(curve))
        times.append(time / 1_000_000_000)    
    
    # PLOTTING
    plt.xlabel("Bin")
    plt.ylabel("Intensity")
    plt.yscale('log')
    plt.title("Spectroscopy (time: " + str(round(times[-1])) + "s, curves stored: " + str(len(times)) + ")")
    # plot all channels summed up    
    total_max = 0
    total_min = 9999999999999
    for i in range(len(channel_curves)):
        sum_curve = np.sum(channel_curves[i], axis=0)
        max = np.max(sum_curve)
        min = np.min(sum_curve)
        if max > total_max:
            total_max = max
        if min < total_min:    
            total_min = min
        plt.plot(sum_curve, label=f"Channel {metadata['channels'][i] + 1}")  
        plt.legend()  
    plt.ylim(min * 0.99, max * 1.01) 
    plt.tight_layout()   
    plt.show()                   
            """,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "with open(file_path, 'rb') as f:",
            "replace_pattern": "with open(file_path, 'rb') as f:",
            "requirements": ["matplotlib", "numpy"],
        }
        ScriptFileUtils.export_script_file(bin_file_path, "py", content_modifier)

    @staticmethod
    def download_phasors(window, bin_file_path):
        content_modifier = {
            "source_file": """import os
import struct
import matplotlib.pyplot as plt
import numpy as np

file_path = "<FILE-PATH>"
with open(file_path, 'rb') as f:
    # First 4 bytes must be SPF1
    if f.read(4) != b"SPF1":
        print("Invalid data file")
        exit(0)

    # Read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))

    # Enabled channels
    channels = metadata.get("channels", [])
    num_channels = len(channels)
    if num_channels == 0:
        print("No enabled channels found.")
        exit(0)
    
    print(
        "Enabled channels: "
        + ", ".join(["Channel " + str(ch + 1) for ch in channels])
    )

    # Bin width (us)
    bin_width_micros = metadata.get("bin_width_micros")
    if bin_width_micros is not None:
        print("Bin width: " + str(bin_width_micros) + "us")
    
    # Acquisition time (duration of the acquisition)
    acquisition_time_millis = metadata.get("acquisition_time_millis")
    if acquisition_time_millis is not None:
        print("Acquisition time: " + str(acquisition_time_millis / 1000) + "s")
    
    # Laser period (ns)
    laser_period_ns = metadata.get("laser_period_ns")
    if laser_period_ns is not None:
        print("Laser period: " + str(laser_period_ns) + "ns")
        
    # Harmonics
    harmonics = metadata.get("harmonics")
    if harmonics is not None:
        print("Harmonics: " + str(harmonics))    
    
    # Tau (ns)
    tau_ns = metadata.get("tau_ns")
    if tau_ns is not None:
        print("Tau: " + str(tau_ns) + "ns")

    data = {}
    try:
        while True:
            for channel in metadata["channels"]:
                if channel not in data:
                    data[channel] = {}
                for harmonic in range(1, metadata['harmonics'] + 1):    
                    if harmonic not in data[channel]:
                        data[channel][harmonic] = []
                    bytes_read = f.read(32)
                    if not bytes_read:
                        raise StopIteration 
                    try:
                        time_ns, channel_name, harmonic_name, g, s = struct.unpack('QIIdd', bytes_read)
                    except struct.error as e:    
                        print(f"Error unpacking data: {e}")
                        raise StopIteration  
                    data[channel][harmonic].append((g, s))
    except StopIteration:
        pass  

# PLOTTING
fig, ax = plt.subplots()
harmonic_colors = plt.cm.viridis(np.linspace(0, 1, max(h for ch in data.values() for h in ch.keys())))
harmonic_colors_dict = {harmonic: color for harmonic, color in enumerate(harmonic_colors, 1)}
for channel, harmonics in data.items():
    theta = np.linspace(0, np.pi, 100)
    x = np.cos(theta)
    y = np.sin(theta)
    ax.plot(x, y, label=f'Channel: {channel + 1}')
    for harmonic, values in harmonics.items():
        if values:
            g_values, s_values = zip(*values)
            g_values = np.array(g_values)
            s_values = np.array(s_values)
            mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
            g_values = g_values[mask]
            s_values = s_values[mask]
            ax.scatter(g_values, s_values, label=f'Channel: {channel + 1} Harmonic: {harmonic}',
                       color=harmonic_colors_dict[harmonic])

ax.set_aspect('equal')    
ax.legend()
plt.title('Phasors Plot')
plt.xlabel('G')
plt.ylabel('S')
plt.grid(True)
plt.show()                                      
            """,
            "skip_pattern": "get_recent_spectroscopy_file():",
            "end_pattern": "with open(file_path, 'rb') as f:",
            "replace_pattern": "with open(file_path, 'rb') as f:",
            "requirements": ["matplotlib", "numpy"],
        }
        ScriptFileUtils.export_script_file(bin_file_path, "py", content_modifier)


class MatlabScriptUtils(ScriptFileUtils):
    @staticmethod
    def download_spectroscopy(window, bin_file_path):
        content_modifier = {
            "source_file": """file_path = '<FILE-PATH>';
% Open the file            
fid = fopen(file_path, 'rb');
if fid == -1
    error('Could not open file');
end

% Check for 'SP01' identifier
sp01 = fread(fid, 4, 'char');
if ~isequal(char(sp01'), 'SP01')
    fprintf('Invalid data file');
    fclose(fid);
    return;
end

% Read metadata
json_length = fread(fid, 1, 'uint32');
metadata_json = fread(fid, json_length, 'char');
metadata = jsondecode(char(metadata_json'));

% Print metadata information
if isfield(metadata, 'channels') && ~isempty(metadata.channels)
    disp(['Enabled channels: ' strjoin(arrayfun(@(ch) ['Channel ' num2str(ch + 1)], metadata.channels, 'UniformOutput', false), ', ')]);
end
if isfield(metadata, 'bin_width_micros') && ~isempty(metadata.bin_width_micros)
    disp(['Bin width: ' num2str(metadata.bin_width_micros) ' us']);
end
if isfield(metadata, 'acquisition_time_millis') && ~isempty(metadata.acquisition_time_millis)
    disp(['Acquisition time: ' num2str(metadata.acquisition_time_millis / 1000) 's']);
end
if isfield(metadata, 'laser_period_ns') && ~isempty(metadata.laser_period_ns)
    disp(['Laser period: ' num2str(metadata.laser_period_ns) 'ns']);
end
if isfield(metadata, 'tau_ns') && ~isempty(metadata.tau_ns)
    disp(['Tau: ' num2str(metadata.tau_ns) 'ns']);
end

num_channels = length(metadata.channels);
channel_curves = cell(1, num_channels);
for i = 1:num_channels
    channel_curves{i} = [];
end
times = [];

% Read data
while ~feof(fid)
    time_data = fread(fid, 1, 'double');
    if isempty(time_data)
        break;
    end
    times = [times; time_data / 1e9];
    
    for i = 1:num_channels
        curve_data = fread(fid, 256, 'uint32');
        if length(curve_data) < 256
            break;
        end
        channel_curves{i} = [channel_curves{i}; curve_data'];
    end
end
fclose(fid);

% Plotting
figure;
hold on;
xlabel('Bin');
ylabel('Intensity');
set(gca, 'YScale', 'log');
title(sprintf('Spectroscopy (time: %.2fs, curves stored: %d)', round(times(end)), length(times)));

total_max = -inf;
total_min = inf;
for i = 1:num_channels
    sum_curve = sum(channel_curves{i}, 1);
    total_max = max(total_max, max(sum_curve));
    total_min = min(total_min, min(sum_curve));
    plot(sum_curve, 'DisplayName', sprintf('Channel %d', metadata.channels(i) + 1));
end

ylim([total_min * 0.99, total_max * 1.01]);
legend show;
hold off;      
            """,
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% Open the file",
            "replace_pattern": "% Open the file",
            "requirements": [],
        }
        ScriptFileUtils.export_script_file(bin_file_path, "m", content_modifier)

    @staticmethod
    def download_phasors(window, bin_file_path):
        content_modifier = {
            "source_file": """file_path = '<FILE-PATH>';
% Open the file            
fid = fopen(file_path, 'rb');
if fid == -1
    error('Could not open file');
end

% Check for 'SPF1' identifier
header = fread(fid, 4, 'char=>char')';
if ~strcmp(header, 'SPF1')
    disp('Invalid data file');
    fclose(fid);
    return;
end

% Read metadata
json_length = fread(fid, 1, 'uint32');
metadata_json = fread(fid, json_length, 'char');
metadata = jsondecode(char(metadata_json'));

% Print metadata information
if isfield(metadata, 'channels') && ~isempty(metadata.channels)
     disp(['Enabled channels: ' strjoin(arrayfun(@(ch) ['Channel ' num2str(ch + 1)], metadata.channels, 'UniformOutput', false), ', ')]);   
end
if isfield(metadata, 'bin_width_micros') && ~isempty(metadata.bin_width_micros)
    disp(['Bin width: ' num2str(metadata.bin_width_micros) ' us']);
end
if isfield(metadata, 'acquisition_time_millis') && ~isempty(metadata.acquisition_time_millis)
    disp(['Acquisition time: ' num2str(metadata.acquisition_time_millis / 1000) 's']);
end
if isfield(metadata, 'laser_period_ns') && ~isempty(metadata.laser_period_ns)
    disp(['Laser period: ' num2str(metadata.laser_period_ns) 'ns']);
end
if isfield(metadata, 'tau_ns') && ~isempty(metadata.tau_ns)
    disp(['Tau: ' num2str(metadata.tau_ns) 'ns']);
end
if isfield(metadata, 'harmonics') && ~isempty(metadata.harmonics)
    disp(['Harmonics: ' num2str(metadata.harmonics)]);
end

data = struct();

% Read data
try
    while true
        for i = 1:length(metadata.channels)
            channel = metadata.channels(i);
            if ~isfield(data, num2str(channel))
                data.(num2str(channel)) = struct();
            end
            for harmonic = 1:metadata.harmonics
                if ~isfield(data.(num2str(channel)), num2str(harmonic))
                    data.(num2str(channel)).(num2str(harmonic)) = [];
                end
                bytes_read = fread(fid, 32, 'uint8');
                if isempty(bytes_read) || numel(bytes_read) < 32
                    error('StopIteration');
                end
                try
                    time_ns = typecast(uint8(bytes_read(1:8)), 'uint64');
                    channel_name = typecast(uint8(bytes_read(9:12)), 'uint32');
                    harmonic_name = typecast(uint8(bytes_read(13:16)), 'uint32');
                    g = typecast(uint8(bytes_read(17:24)), 'double');
                    s = typecast(uint8(bytes_read(25:32)), 'double');
                catch
                    disp('Error unpacking data');
                    error('StopIteration');
                end
                data.(num2str(channel)).(num2str(harmonic)) = [data.(num2str(channel)).(num2str(harmonic)); g, s];
            end
        end
    end
catch
end
fclose(fid);

% PLOTTING
figure;
hold on;

harmonics_colors = jet(max(cellfun(@(ch) length(fieldnames(data.(ch))), fieldnames(data))));
unit_circle_colors = lines(length(fieldnames(data)));

channels = fieldnames(data);

for i = 1:length(channels)
    channel = channels{i};
    harmonics = fieldnames(data.(channel));
    for j = 1:length(harmonics)
        harmonic = harmonics{j};
        values = data.(channel).(harmonic);
        if ~isempty(values)
            g_values = values(:, 1);
            s_values = values(:, 2);
            mask = (abs(g_values) < 1e9) & (abs(s_values) < 1e9);
            g_values = g_values(mask);
            s_values = s_values(mask);
            scatter(g_values, s_values, [], harmonics_colors(str2double(harmonic), :), 'filled', ...
                    'DisplayName', sprintf('Channel: %d Harmonic: %d', str2double(channel) + 1, str2double(harmonic)));
        end
    end
end

for i = 1:length(channels)
    channel = channels{i};
    theta = linspace(0, pi, 100);
    x = cos(theta);
    y = sin(theta);
    plot(x, y, 'Color', unit_circle_colors(i, :), 'LineWidth', 1, 'DisplayName', sprintf('Channel: %d', str2double(channel) + 1));
end

axis equal;
xlabel('G');
ylabel('S');
title('Phasors Plot');
legend('Location', 'southwest');
grid on;
hold off;
                                     
            """,
            "skip_pattern": "% Get the recent phasors file",
            "end_pattern": "% Open the file",
            "replace_pattern": "% Open the file",
            "requirements": [],
        }
        ScriptFileUtils.export_script_file(bin_file_path, "m", content_modifier)
