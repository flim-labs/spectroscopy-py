file_path = '<FILE-PATH>';
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
