spectroscopy_file_path = "<FILE-PATH>";
laserblood_metadata_file_path = "<LASERBLOOD-METADATA-FILE-PATH>"

% READ LASERBLOOD EXPERIMENT METADATA
laserblood_metadata_str = fileread(laserblood_metadata_file_path);
laserblood_data = jsondecode(laserblood_metadata_str);
laserblood_fields = fieldnames(laserblood_data);
for i = 1:numel(laserblood_fields)
    key = laserblood_fields{i};
    value = laserblood_data.(key);
    if isnumeric(value)
        value = num2str(value);
    elseif islogical(value)
        value = mat2str(value);
    end
    fprintf('%s: %s\n', key, value);
end

% Open spectroscopy bin file            
fid = fopen(spectroscopy_file_path, 'rb');
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

% Read bin metadata
json_length = fread(fid, 1, 'uint32');
metadata_json = fread(fid, json_length, 'char');
metadata = jsondecode(char(metadata_json'));
enabled_channels = sprintf('Channel %d, ', metadata.channels + 1);
laser_period_ns = metadata.laser_period_ns;

num_channels = length(metadata.channels);
channel_curves = cell(1, num_channels);
for i = 1:num_channels
    channel_curves{i} = [];
end
times = [];

% Read bin data
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

% Calculate the x-axis values based on the laser period
num_bins = 256;
x_values = linspace(0, laser_period_ns, num_bins);

% Plotting
figure;
hold on;
xlabel(sprintf('Time (ns, Laser period = %d ns)', laser_period_ns));
ylabel('Intensity');
title(sprintf('Spectroscopy (time: %.2fs, curves stored: %d)', round(times(end)), length(times)));

total_max = -inf;
total_min = inf;
for i = 1:num_channels
    sum_curve = sum(channel_curves{i}, 1);
    total_max = max(total_max, max(sum_curve));
    total_min = min(total_min, min(sum_curve));
    plot(x_values, sum_curve, 'DisplayName', sprintf('Channel %d', metadata.channels(i) + 1));
end

ylim([total_min * 0.99, total_max * 1.01]);
legend show;
hold off;