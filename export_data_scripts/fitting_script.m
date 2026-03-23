spectroscopy_file_path = '<SPECTROSCOPY-FILE-PATH>';
fitting_file_path = '<FITTING-FILE-PATH>';

% Custom channel names (if any)
channel_names_json = '<CHANNEL-NAMES>';
try
    channel_names = jsondecode(channel_names_json);
catch
    channel_names = struct();
end

% Helper function for channel names
function name = get_channel_name(channel_id, custom_names)
    field_name = sprintf('x%d', channel_id);
    if isfield(custom_names, field_name)
        custom_name = custom_names.(field_name);
        if length(custom_name) > 30
            custom_name = [custom_name(1:30) '...'];
        end
        name = sprintf('%s (Ch%d)', custom_name, channel_id + 1);
    else
        name = sprintf('Channel %d', channel_id + 1);
    end
end

% ===== READ SPECTROSCOPY FILE - ONLY FOR METADATA =====
fprintf('Reading spectroscopy file: %s\n', spectroscopy_file_path);

fid = fopen(spectroscopy_file_path, 'rb');
if fid == -1
    error('Could not open spectroscopy file');
end

% Check for 'SP01' identifier
sp01 = fread(fid, 4, 'char');
if ~isequal(char(sp01'), 'SP01')
    fprintf('Invalid spectroscopy data file\n');
    fclose(fid);
    return;
end

% Read metadata
json_length = fread(fid, 1, 'uint32');
metadata_json = fread(fid, json_length, 'char');
metadata = jsondecode(char(metadata_json'));
fclose(fid);  % Close file - we only need metadata

% Print spectroscopy metadata
fprintf('\n=== SPECTROSCOPY METADATA ===\n');
if isfield(metadata, 'channels') && ~isempty(metadata.channels)
    fprintf('Channels: %d\n', length(metadata.channels));
end
if isfield(metadata, 'bin_width_micros')
    fprintf('Bin Width: %.4f µs\n', metadata.bin_width_micros);
end
if isfield(metadata, 'acquisition_time_millis')
    fprintf('Acquisition Time: %d ms\n', metadata.acquisition_time_millis);
end
if isfield(metadata, 'laser_period_ns')
    fprintf('Laser Period: %.2f ns\n', metadata.laser_period_ns);
end
if isfield(metadata, 'tau_ns')
    fprintf('Tau: %.2f ns\n', metadata.tau_ns);
end

% ===== READ FITTING RESULTS FROM JSON FILE =====
fprintf('\n=== LOADING FITTING RESULTS ===\n');
fprintf('Reading fitting file: %s\n', fitting_file_path);

fitting_fid = fopen(fitting_file_path, 'r');
if fitting_fid == -1
    error('Failed to open fitting file: %s', fitting_file_path);
end
fitting_json_str = fread(fitting_fid, '*char')';
fclose(fitting_fid);
fitting_results = jsondecode(fitting_json_str);

if isempty(fitting_results)
    error('No fitting results found in JSON file.');
end

% Print fitting metadata (from first result)
fprintf('\n=== FITTING METADATA ===\n');
uses_deconvolution = false;
if isfield(fitting_results(1), 'use_deconvolution') && fitting_results(1).use_deconvolution
    uses_deconvolution = true;
    fprintf('Deconvolution: YES\n');
    if isfield(fitting_results(1), 'irf_tau_ns')
        fprintf('IRF Tau: %.4f ns\n', fitting_results(1).irf_tau_ns);
    end
    if isfield(fitting_results(1), 'laser_period_ns')
        fprintf('IRF Laser Period: %.2f ns\n', fitting_results(1).laser_period_ns);
    end
else
    fprintf('Deconvolution: NO\n');
end
fprintf('Channels fitted: %d\n', length(fitting_results));
fprintf('\n');

% ===== EXTRACT RESULTS FROM FITTING JSON =====
valid_results = {};

for i = 1:length(fitting_results)
    result_data = fitting_results(i);
    
    % Get time and count data
    time_values = result_data.x_values;
    t_data = result_data.t_data;
    y_data = result_data.y_data;
    fitted_values = result_data.fitted_values;
    residuals = result_data.residuals;
    scale_factor = result_data.scale_factor;
    decay_start = result_data.decay_start;
    channel_index = result_data.channel;
    fitted_params_text = result_data.fitted_params_text;
    
    % Get raw signal and IRF if available
    raw_signal = [];
    if isfield(result_data, 'raw_signal')
        raw_signal = result_data.raw_signal;
    end
    
    irf_reference = [];
    if isfield(result_data, 'irf_reference')
        irf_reference = result_data.irf_reference;
    end
    
    % Create result structure
    result = struct( ...
        'time_values', time_values, ...
        't_data', t_data, ...
        'y_data', y_data, ...
        'fitted_values', fitted_values, ...
        'residuals', residuals, ...
        'scale_factor', scale_factor, ...
        'decay_start', decay_start, ...
        'channel', channel_index, ...
        'raw_signal', raw_signal, ...
        'irf_reference', irf_reference, ...
        'fitted_params_text', fitted_params_text ...
    );
    
    valid_results{end + 1} = result;
    
    % Display fitting parameters
    fprintf('Fitting parameters for channel %d:\n', channel_index + 1);
    fprintf('%s\n', result.fitted_params_text);
end

% ===== CREATE PLOTS =====
num_plots = numel(valid_results);
plots_per_row = 4;
num_rows = ceil(num_plots / plots_per_row);

% Create a figure
fig = figure('Color', 'black', 'Position', [100, 100, 1000, 500 * num_rows + 100]);

% Define colors
lime_color = [0.5, 1, 0];     % RGB for lime
red_color = [1, 0, 0];        % RGB for red
cyan_color = [0, 1, 1];       % RGB for cyan
orange_color = [1, 0.647, 0]; % RGB for orange
white_color = [1, 1, 1];      % RGB for white
black_color = [0, 0, 0];      % RGB for black

% Create axes for plots and residuals
for row = 1:num_rows
    for col = 1:plots_per_row
        % Calculate index for current subplot
        idx = (row - 1) * plots_per_row + col;
        if idx > num_plots
            break;
        end
        
        % Extract result data
        result = valid_results{idx};
        x_values = result.time_values;
        t_data = result.t_data;
        y_data = result.y_data;
        fitted_values = result.fitted_values;
        residuals = result.residuals;
        scale_factor = result.scale_factor;
        decay_start = result.decay_start + 1;  % MATLAB is 1-indexed
        channel_index = result.channel;
        
        % Scale data back to counts (same as Python)
        truncated_x_values = x_values(decay_start:end);
        counts_y_data = y_data * scale_factor;
        fitted_y_data = fitted_values * scale_factor;
        
        % Create plot axes
        subplot(num_rows * 2, plots_per_row, (row - 1) * plots_per_row + col, 'Parent', fig);
        hold on;
        
        % Main plot: Counts vs Fitted curve
        h1 = scatter(truncated_x_values, counts_y_data, 1, 'MarkerEdgeColor', lime_color);
        h2 = plot(t_data, fitted_y_data, 'Color', red_color, 'LineWidth', 2);
        
        % Collect handles and labels for legend
        handles = [h1, h2];
        if uses_deconvolution
            labels = {'Deconv Counts', 'Fitted curve'};
        else
            labels = {'Counts', 'Fitted curve'};
        end
        
        % If deconvolution was used, also plot raw signal and IRF
        if uses_deconvolution && ~isempty(result.raw_signal)
            raw_signal = result.raw_signal;
            h3 = scatter(x_values, raw_signal, 1, 'MarkerEdgeColor', cyan_color, ...
                'MarkerFaceColor', cyan_color, 'MarkerEdgeAlpha', 0.5, 'MarkerFaceAlpha', 0.5);
            handles = [handles, h3];
            labels = [labels, {'Raw signal'}];
            
            % Plot IRF on same axis (normalized to be visible)
            if ~isempty(result.irf_reference)
                irf_reference = result.irf_reference;
                irf_max = max(irf_reference);
                if irf_max > 0
                    % Normalize IRF to same scale as counts
                    irf_normalized = irf_reference / irf_max * max(counts_y_data) * 0.8;
                    h4 = plot(x_values, irf_normalized, '--', 'Color', orange_color, ...
                        'LineWidth', 2);
                    handles = [handles, h4];
                    labels = [labels, {'IRF'}];
                end
            end
        end
        
        % Set axis properties
        xlabel('Time (ns)', 'Color', white_color);
        ylabel('Counts', 'Color', white_color);
        
        % Add deconvolution status to title
        title_str = get_channel_name(channel_index, channel_names);
        if uses_deconvolution
            title_str = sprintf('%s (Deconv = True)', title_str);
        else
            title_str = sprintf('%s (Deconv = False)', title_str);
        end
        title(title_str, 'Color', white_color);
        
        % Create combined legend with all handles
        legend(handles, labels, 'Location', 'northeast', ...
            'TextColor', white_color, 'Color', black_color);
        
        set(gca, 'Color', black_color, 'XColor', white_color, 'YColor', white_color);
        grid on;
        set(gca, 'GridColor', white_color, 'GridLineStyle', '--', 'GridAlpha', 0.5);
        
        % Create residual plot axes
        subplot(num_rows * 2, plots_per_row, num_rows * plots_per_row + (row - 1) * plots_per_row + col, 'Parent', fig);
        hold on;
        
        % Plot residuals
        plot(truncated_x_values, residuals, 'Color', cyan_color, 'LineWidth', 1);
        
        % Add horizontal line at y=0
        line(xlim, [0, 0], 'Color', white_color, 'LineStyle', '--', 'LineWidth', 0.5);
        
        % Set axis properties
        xlabel('Time (ns)', 'Color', white_color);
        ylabel('Residuals', 'Color', white_color);
        set(gca, 'Color', black_color, 'XColor', white_color, 'YColor', white_color);
        grid on;
        set(gca, 'GridColor', white_color, 'GridLineStyle', '--', 'GridAlpha', 0.5);

        ax_pos = get(gca, 'Position');
        new_height = ax_pos(4) * 0.5; 
        new_y = ax_pos(2) + ax_pos(4) - new_height;  
        set(gca, 'Position', [ax_pos(1), new_y, ax_pos(3), new_height]);
        
        % Display fitting parameters below the residuals plot
        if ~isempty(result.fitted_params_text)
            text_x = ax_pos(1) + 0.01;
            text_y = ax_pos(2)  
            text_width = ax_pos(3) - 0.05;
            text_height = ax_pos(4) * 0.4; 
            
            annotation('textbox', [text_x, text_y, text_width, text_height], ...
                'String', result.fitted_params_text, ...
                'FontSize', 11, ...
                'Color', white_color, ...
                'BackgroundColor', black_color, ...
                'EdgeColor', 'none', ...
                'VerticalAlignment', 'top', ...
                'HorizontalAlignment', 'left', ...
                'Interpreter', 'none', ...
                'Margin', 8);
        end
    end
end

% Turn off the axis for empty plots
for i = num_plots + 1:num_rows * plots_per_row
    row = ceil(i / plots_per_row);
    col = mod(i - 1, plots_per_row) + 1;
    
    % Turn off the plot and residuals axes
    subplot(num_rows * 2, plots_per_row, (row - 1) * plots_per_row + col, 'Parent', fig);
    axis off;
    
    subplot(num_rows * 2, plots_per_row, num_rows * plots_per_row + (row - 1) * plots_per_row + col, 'Parent', fig);
    axis off;
end
