spectroscopy_file_path = '<SPECTROSCOPY-FILE-PATH>'
phasors_file_path = '<PHASORS-FILE-PATH>'
laserblood_metadata_file_path = '<LASERBLOOD-METADATA-FILE-PATH>'
fprintf('Using data file: %s\n', phasors_file_path);

% READ LASERBLOOD EXPERIMENT METADATA
laserblood_metadata_str = fileread(laserblood_metadata_file_path);
laserblood_data = jsondecode(laserblood_metadata_str);
fprintf('\n');
for i = 1:numel(laserblood_data)
    item = laserblood_data(i);
    label = item.label;
    unit = strtrim(item.unit);
    if ~isempty(unit)
        label = sprintf('%s (%s)', label, unit);
    end
    value = item.value;
    if isnumeric(value)
        value = num2str(value);
    elseif islogical(value)
        value = mat2str(value);
    end
    fprintf('%s: %s\n', label, value);
end

% READ SPECTROSCOPY DATA
spectroscopy_fid = fopen(spectroscopy_file_path, 'rb');
if spectroscopy_fid == -1
    error('Could not open file');
end
sp01 = fread(spectroscopy_fid, 4, 'char');
if ~isequal(char(sp01'), 'SP01')
    fprintf('Invalid data file\n');
    fclose(spectroscopy_fid);
    return;
end
spectroscopy_json_length = fread(spectroscopy_fid, 1, 'uint32');
spectroscopy_metadata_json = fread(spectroscopy_fid, spectroscopy_json_length, 'char');
spectroscopy_metadata = jsondecode(char(spectroscopy_metadata_json'));
spectro_num_channels = length(spectroscopy_metadata.channels);
channel_curves = cell(1, spectro_num_channels);
for i = 1:spectro_num_channels
    channel_curves{i} = [];
end
times = [];
while ~feof(spectroscopy_fid)
    time_data = fread(spectroscopy_fid, 1, 'double');
    if isempty(time_data)
        break;
    end
    times = [times; time_data / 1e9];
    for i = 1:spectro_num_channels
        curve_data = fread(spectroscopy_fid, 256, 'uint32');
        if length(curve_data) < 256
            break;
        end
        channel_curves{i} = [channel_curves{i}; curve_data'];
    end
end
fclose(spectroscopy_fid);

% Calculate the x-axis values based on the laser period
if isfield(spectroscopy_metadata, 'laser_period_ns') && ~isempty(spectroscopy_metadata.laser_period_ns)
    laser_period_ns = spectroscopy_metadata.laser_period_ns;
    fprintf('Laser period: %dns\n', laser_period_ns);
else
    error('Laser period not found in metadata.');
end
num_bins = 256;
x_values = linspace(0, laser_period_ns, num_bins);

% READ PHASORS DATA
phasors_fid = fopen(phasors_file_path, 'rb');
if phasors_fid == -1
    error('Could not open file');
end
phasors_header = fread(phasors_fid, 4, 'char=>char')';
if ~strcmp(phasors_header, 'SPF1')
    disp('Invalid data file');
    fclose(phasors_fid);
    return;
end
phasors_json_length = fread(phasors_fid, 1, 'uint32');
phasors_metadata_json = fread(phasors_fid, phasors_json_length, 'char');
phasors_metadata = jsondecode(char(phasors_metadata_json'));
fprintf('Enabled channels: %s\n', sprintf('Channel %d, ', phasors_metadata.channels + 1));
fprintf('Bin width: %dus\n', phasors_metadata.bin_width_micros);
fprintf('Acquisition time: %.2fs\n', phasors_metadata.acquisition_time_millis / 1000);
fprintf('Laser period: %dns\n', phasors_metadata.laser_period_ns);
if isfield(phasors_metadata, 'tau_ns') && ~isempty(phasors_metadata.tau_ns)
    fprintf('Tau: %dns\n', phasors_metadata.tau_ns);
end
disp(['Harmonics: ' num2str(phasors_metadata.harmonics)]);

phasors_data = struct();
try
    while true
        bytes_read = fread(phasors_fid, 32, 'uint8');
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
        if ~isfield(phasors_data, num2str(channel_name))
            phasors_data.(num2str(channel_name)) = struct();
        end
        if !isfield(phasors_data.(num2str(channel_name)), num2str(harmonic_name))
            phasors_data.(num2str(channel_name)).(num2str(harmonic_name)) = [];
        end
        phasors_data.(num2str(channel_name)).(num2str(harmonic_name)) = ...
            [phasors_data.(num2str(channel_name)).(num2str(harmonic_name)); g, s];
    end
catch
end
fclose(phasors_fid);

% PLOTTING
num_channels = length(fieldnames(phasors_data));
max_plots_per_row = 3;
num_rows = ceil((num_channels + 1) / max_plots_per_row);
figure;
points_colors = [
    0.4 0.6 0.8; 
    0.8 0.6 0.4;  
    0.8 0.7 0.4; 
    0.6 0.4 0.8;  
];

x_colors = [
    0.4940 0.1840 0.5560;  
    0.8500 0.3250 0.0980;  
    0.9290 0.6940 0.1250;  
    0 0.4470 0.7410;      
];

% Plot Spectroscopy Data
subplot(num_rows, max_plots_per_row, 1);
hold on;
xlabel(sprintf('Time (ns, Laser period = %d ns)', laser_period_ns));
ylabel('Intensity');
title(sprintf('Spectroscopy (time: %.2fs, curves stored: %d)', round(times(end)), length(times)));

total_max = -inf;
total_min = inf;
for i = 1:spectro_num_channels
    sum_curve = sum(channel_curves{i}, 1);
    total_max = max(total_max, max(sum_curve));
    total_min = min(total_min, min(sum_curve));
    plot(x_values, sum_curve, 'DisplayName', sprintf('Channel %d', spectroscopy_metadata.channels(i) + 1));
end
ylim([total_min * 0.99, total_max * 1.01]);
xlim([0, laser_period_ns]);
hold off;
legend('Location', 'southeast', 'FontSize', 12);

channels = fieldnames(phasors_data);
plot_index = 2;

for i = 1:length(channels)
    channel = channels{i};
    harmonics = fieldnames(phasors_data.(channel));
    subplot(num_rows, max_plots_per_row, plot_index);
    hold on;
    x = linspace(0, 1, 1000);
    y = sqrt(0.5^2 - (x - 0.5).^2);
    plot(x, y, 'k-', 'HandleVisibility', 'off');

    for j = 1:length(harmonics)
        harmonic = harmonics{j};
        values = phasors_data.(channel).(harmonic);
        if ~isempty(values)
            g_values = values(:, 1);
            s_values = values(:, 2);
            mask = (abs(g_values) < 1e9) & (abs(s_values) < 1e9);
            g_values = g_values(mask);
            s_values = s_values(mask);

            scatter(g_values, s_values, [], points_colors(mod(j-1, 4) + 1, :), 'filled', ...
                    'DisplayName', sprintf('Harmonic: %d', str2double(harmonic)));

            mean_g = mean(g_values);
            mean_s = mean(s_values);

            freq_mhz = 1 / (phasors_metadata.laser_period_ns * 1e-9) / 1e6;
            tau_phi = (1 / (2 * pi * freq_mhz * str2double(harmonic))) * (mean_s / mean_g) * 1e3;
            tau_m_component = (1 / (mean_s^2 + mean_g^2)) - 1;
            tau_m = (1 / (2 * pi * freq_mhz * str2double(harmonic))) * sqrt(tau_m_component) * 1e3;
            if tau_m_component < 0
                tau_m = NaN;
            end

            scatter(mean_g, mean_s, 100, 'x', 'MarkerEdgeColor', x_colors(mod(j-1, 4) + 1, :), 'LineWidth', 2, ...
                    'DisplayName', sprintf('G (mean): %.2f, S (mean): %.2f, \\tau_\\phi: %.2f ns, \\tau_m: %.2f ns', ...
                                           mean_g, mean_s, tau_phi, tau_m));            
        end
    end

    title(sprintf('Phasors - Channel %d', str2double(channel) + 1));
    legend('Location', 'southeast', 'FontSize', 12);
    xlabel('G');
    ylabel('S');
    grid on;
    hold off;
    plot_index = plot_index + 1;
end
