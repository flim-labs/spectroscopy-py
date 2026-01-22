% ⚠ WARNING: To run this script you need the "optim" package or the Optimization Toolbox installed ⚠

file_path = '<FILE-PATH>';

% Open the file            
fid = fopen(file_path, 'rb');
if fid == -1
    error('Could not open file');
end

% Check for 'SP01' identifier
sp01 = fread(fid, 4, 'char');
if ~isequal(char(sp01'), 'SP01')
    fprintf('Invalid data file\n');
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
if isfield(metadata, 'bin_width_micros')
    fprintf('Bin width: %dus\n', metadata.bin_width_micros);
end
if isfield(metadata, 'acquisition_time_millis')
    fprintf('Acquisition time: %.2fs\n', metadata.acquisition_time_millis / 1000);
end
if isfield(metadata, 'laser_period_ns')
    laser_period_ns = metadata.laser_period_ns;
    fprintf('Laser period: %dns\n', laser_period_ns);
else
    error('Laser period not found in metadata.');
end
if isfield(metadata, 'tau_ns')
    fprintf('Tau: %dns\n', metadata.tau_ns);
end

num_channels = length(metadata.channels);
channel_curves = cell(1, num_channels);
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
        if numel(curve_data) < 256
            break;
        end
        channel_curves{i} = [channel_curves{i}; curve_data'];
    end
end
fclose(fid);

num_bins = 256;
x_values = linspace(0, laser_period_ns, num_bins);

% Function definition for fitting
function result = fit_decay_curve(x_values, y_values, channel)
    % Define decay models
    decay_model_1_with_B = @(p, t) p(1) * exp(-t / p(2)) + p(3);
    decay_model_2_with_B = @(p, t) p(1) * exp(-t / p(2)) + p(3) * exp(-t / p(4)) + p(5);
    decay_model_3_with_B = @(p, t) p(1) * exp(-t / p(2)) + p(3) * exp(-t / p(4)) + p(5) * exp(-t / p(6)) + p(7);
    decay_model_4_with_B = @(p, t) p(1) * exp(-t / p(2)) + p(3) * exp(-t / p(4)) + p(5) * exp(-t / p(6)) + p(7) * exp(-t / p(8)) + p(9);

    % Model formulas for display
    model_formulas = { ...
        'A1 * exp(-t / tau1) + B', ...
        'A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + B', ...
        'A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + B', ...
        'A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + A4 * exp(-t / tau4) + B' ...
    };

    % Define decay models and initial guesses
    decay_models = { ...
        {decay_model_1_with_B, [1, 1, 1]}, ...
        {decay_model_2_with_B, [1, 1, 1, 1, 1]}, ...
        {decay_model_3_with_B, [1, 1, 1, 1, 1, 1, 1]}, ...
        {decay_model_4_with_B, [1, 1, 1, 1, 1, 1, 1, 1, 1]} ...
    };

    % Start fitting at the point where y_values is maximal
    decay_start = find(y_values == max(y_values), 1, 'first');

    % check if all y_values are zero
    if sum(y_values) == 0
        result.error = 'All counts are zero.';
        return;
    end

    % Scale big y_values 
    scale_factor = 1;
    if max(y_values) > 1000
        scale_factor = max(y_values) / 1000;
        y_values = y_values / scale_factor;
    end
    
    t_data = x_values(decay_start:end);
    y_data = y_values(decay_start:end);

    best_chi2 = inf;
    best_fit = [];
    best_model = [];
    best_popt = [];
    tau_similarity_threshold = 0.01;  % Definisci una soglia di somiglianza per i valori di tau

    for i = 1:length(decay_models)
        model = decay_models{i}{1};
        initial_guess = decay_models{i}{2};

        try
            % Set options for lsqcurvefit
            opts = optimset('Display', 'off', 'TolFun', 1e-8, 'TolX', 1e-8, 'MaxFunEvals', 10000000);
            % Fit model to data
            [popt, ~, residual, ~] = lsqcurvefit(model, initial_guess, t_data, y_data, [], [], opts);
            fitted_values = model(popt, t_data);

            % Calculate Chi-square
            epsilon = 1e-10;
            chi2 = sum((y_data - fitted_values).^2 ./ (fitted_values + epsilon));
            reduced_chi2 = chi2 / (length(y_data) - length(popt));

            if reduced_chi2 < best_chi2
                best_chi2 = reduced_chi2;
                best_fit = fitted_values;
                best_model = model;
                best_popt = popt;
            end

        catch ME
            fprintf('Model fitting failed: %s\n', ME.message);
            % Skip models that fail
            continue;
        end
    end

    if isempty(best_fit)
        result.error = 'Optimal parameters not found for any model.';
        return;
    end

    % Check for τ values similarity and remove redundant components
    num_components = (length(best_popt) - 1) / 2;
    tau_values = best_popt(2:2:end-1);
    
    % Identify groups of similar tau values
    similar_groups = {};
    used_indices = [];
    
    for i = 1:length(tau_values)
        if ismember(i, used_indices)
            continue;
        end
        
        group = i;
        for j = (i+1):length(tau_values)
            if ismember(j, used_indices)
                continue;
            end
            
            % Use max of the two values as denominator to avoid division by small numbers
            denominator = max([abs(tau_values(i)), abs(tau_values(j)), 1e-10]);
            relative_diff = abs(tau_values(i) - tau_values(j)) / denominator;
            
            if relative_diff < tau_similarity_threshold
                group = [group, j];
                used_indices = [used_indices, j];
            end
        end
        
        similar_groups{end+1} = group;
        used_indices = [used_indices, i];
    end
    
    % If we have redundant components, simplify the model
    has_redundant_components = any(cellfun(@length, similar_groups) > 1);
    unique_components = length(similar_groups);
    
    if has_redundant_components && unique_components < num_components
        % Refit with the appropriate model based on unique components
        if unique_components == 1
            model = decay_model_1_with_B;
            initial_guess = [1, 1, 1];
        elseif unique_components == 2
            model = decay_model_2_with_B;
            initial_guess = [1, 1, 1, 1, 1];
        elseif unique_components == 3
            model = decay_model_3_with_B;
            initial_guess = [1, 1, 1, 1, 1, 1, 1];
        else
            model = best_model;
        end
        
        % Refit only if we're simplifying
        if unique_components < num_components
            try
                [best_popt, ~, residual, ~] = lsqcurvefit(model, initial_guess, t_data, y_data, [], [], opts);
                best_fit = model(best_popt, t_data);
                best_model = model;
                num_components = (length(best_popt) - 1) / 2;
                best_chi2 = sum((y_data - best_fit).^2 ./ (best_fit + epsilon)) / (length(y_data) - length(best_popt));
            catch
                % If refit fails, keep the original best fit
            end
        end
    end

    % Prepare output data
    output_data = struct();
    fitted_params_text = '';

    for i = 1:num_components
        y = (i - 1) * 2 + 1;
        SUM = sum(best_popt(1:2:end-1));
        percentage_tau = best_popt(y) / (SUM + best_popt(end));
        fitted_params_text = sprintf('%sτ%d = %.4f ns, %.2f%% of total\n', fitted_params_text, i, best_popt(y + 1), percentage_tau * 100);
        output_data.(['component_A', num2str(i)]) = struct('tau_ns', best_popt(y + 1), 'percentage', percentage_tau);
    end

    SUM = sum(best_popt(1:2:end-1));
    percentage_tau = best_popt(end) / (SUM + best_popt(end));
    fitted_params_text = sprintf('%sB = %.2f%% of total\n', fitted_params_text, percentage_tau * 100);
    output_data.component_B = best_popt(end);

    fitted_params_text = sprintf('%sX² = %.4f, ', fitted_params_text, best_chi2);
    model_index = find(cellfun(@(f) isequal(f, best_model), decay_models(:,1)), 1);
    residuals = y_data - best_fit;
    SStot = sum((y_data - mean(y_data)).^2);
    SSres = sum(residuals.^2); 
    % R^2
    r2 = 1 - SSres / SStot;
    fitted_params_text = sprintf('%sR² = %.4f\n', fitted_params_text, r2);
    
    if isempty(model_index)
        model_str = 'Unknown model';
    else
        model_str = model_formulas{model_index};
    end

    % Return results
    result = struct( ...
        'x_values', x_values, ...
        't_data', t_data, ...
        'y_data', y_data, ...
        'fitted_values', best_fit, ...
        'residuals', residuals, ...
        'fitted_params_text', fitted_params_text, ...
        'output_data', output_data, ...
        'scale_factor', scale_factor, ...
        'decay_start', decay_start, ...
        'channel', channel, ...
        'chi2', best_chi2, ...
        'r2', r2, ...
        'model', model_str ...
    );
end

valid_results = {};

for i = 1:numel(channel_curves)
    channel = metadata.channels(i);
    y = sum(channel_curves{i}, 1);
    if isscalar(y)
        y = y(:);
    end
    x = x_values;
    result = fit_decay_curve(x, y, channel);
    
    if isfield(result, 'error')
        fprintf('Skipping channel %d: %s\n', channel + 1, result.error);
        continue;
    end
    
    % Display fitting parameters information
    fprintf('Fitting parameters for channel %d:\n', channel + 1);
    fprintf('%s\n', result.fitted_params_text);
    
    valid_results{end + 1} = result;
end

% Number of valid results/plots
num_plots = numel(valid_results);
plots_per_row = 4;
num_rows = ceil(num_plots / plots_per_row);

% Create a figure
fig = figure('Color', 'black', 'Position', [100, 100, 1000, 500 * num_rows + 100]);

% Define colors
lime_color = [0.5, 1, 0]; % RGB for lime
red_color = [1, 0, 0];    % RGB for red
cyan_color = [0, 1, 1];   % RGB for cyan
white_color = [1, 1, 1];  % RGB for white
black_color = [0, 0, 0];  % RGB for black

% Create axes for plots and residuals
axes_handles = zeros(num_rows * 2, plots_per_row);
for row = 1:num_rows
    for col = 1:plots_per_row
        % Calculate index for current subplot
        idx = (row - 1) * plots_per_row + col;
        if idx > num_plots
            break;
        end
        
        % Create plot axes
        axes_handles(row, col) = subplot(num_rows * 2, plots_per_row, (row - 1) * plots_per_row + col, 'Parent', fig);
        hold on;

        % Extract result data
        result = valid_results{idx};
        truncated_x_values = result.x_values(result.decay_start:end);
        counts_y_data = result.y_data * result.scale_factor;
        fitted_y_data = result.fitted_values * result.scale_factor;
        residuals = result.residuals;

        % Plot data and fitted curve
        h1 = scatter(truncated_x_values, counts_y_data, 1, 'MarkerEdgeColor', lime_color);
        hold on;
        h2 = plot(result.t_data, fitted_y_data, 'Color', red_color, 'LineWidth', 1.5);
        legend([h1, h2], {'Counts', 'Fitted curve'}, 'Location', 'northeast', 'TextColor', white_color, 'Color', black_color);

        % Set axis properties
        xlabel('Time', 'Color', white_color);
        ylabel('Counts', 'Color', white_color);
        title(sprintf('Channel %d', result.channel + 1), 'Color', white_color);
        set(gca, 'Color', black_color, 'XColor', white_color, 'YColor', white_color);
        grid on;
        set(gca, 'GridColor', white_color, 'GridLineStyle', '--', 'GridAlpha', 0.5);
        
        % Set axis limits
        ylim([0, max(counts_y_data) * 1.1]);

        % Create residual plot axes
        subplot(num_rows * 2, plots_per_row, num_rows * plots_per_row + (row - 1) * plots_per_row + col, 'Parent', fig);
        hold on;
        
        % Plot residuals
        plot(truncated_x_values, residuals, 'Color', cyan_color, 'LineWidth', 1);

        % Add horizontal line at y=0
        line(xlim, [0, 0], 'Color', white_color, 'LineStyle', '--', 'LineWidth', 0.5);

        % Set axis properties
        xlabel('Time', 'Color', white_color);
        ylabel('Residuals', 'Color', white_color);
        set(gca, 'Color', black_color, 'XColor', white_color, 'YColor', white_color);
        grid on;
        set(gca, 'GridColor', white_color, 'GridLineStyle', '--', 'GridAlpha', 0.5);
        
        % Set axis limits
        ylim([min(residuals) * 1.1, max(residuals) * 1.1]);

        % Add text box with fitting parameters
        if ~isempty(result.fitted_params_text)
            text(0.02, -0.15, result.fitted_params_text, 'Units', 'normalized', 'FontSize', 10, ...
                 'VerticalAlignment', 'top', 'HorizontalAlignment', 'left', 'Color', white_color, ...
                 'Margin', 2); 
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
