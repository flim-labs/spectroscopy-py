% Get the recent phasors file
userprofile = getenv('USERPROFILE');
data_folder = fullfile(userprofile, '.flim-labs', 'data');

files = dir(fullfile(data_folder, 'spectroscopy-phasors*'));
file_names = {files.name};
is_phasors = cellfun(@(x) isempty(strfind(x, 'calibration')), file_names);
phasors_files = files(is_phasors);
[~, idx] = sort([phasors_files.datenum], 'descend');
file_path = fullfile(data_folder, phasors_files(idx(1)).name);
fprintf('Using data file: %s\n', file_path);

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
    enabled_channels = sprintf('Channel %d, ', metadata.channels + 1);
    fprintf('Enabled channels: %s\n', enabled_channels(1:end-2));
end
if isfield(metadata, 'bin_width_micros') && ~isempty(metadata.bin_width_micros)
    fprintf('Bin width: %dus\n', metadata.bin_width_micros);
end
if isfield(metadata, 'acquisition_time_millis') && ~isempty(metadata.acquisition_time_millis)
    fprintf('Acquisition time: %.2fs\n', metadata.acquisition_time_millis / 1000);
end
if isfield(metadata, 'laser_period_ns') && ~isempty(metadata.laser_period_ns)
    fprintf('Laser period: %dns\n', metadata.laser_period_ns);
end
if isfield(metadata, 'tau_ns') && ~isempty(metadata.tau_ns)
    fprintf('Tau: %dns\n', metadata.tau_ns);
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
