[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path ([Environment]::GetFolderPath("Desktop")) "EyesOnU-AI-Worker.exe")
)

$ErrorActionPreference = "Stop"
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$source = @'
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool createdNew;
        using (Mutex mutex = new Mutex(true, "Local\\EyesOnU-AI-Worker-GUI", out createdNew))
        {
            if (!createdNew)
            {
                MessageBox.Show(
                    "EyesOnU AI Worker GUI\uAC00 \uC774\uBBF8 \uC2E4\uD589 \uC911\uC785\uB2C8\uB2E4.",
                    "EyesOnU AI Worker",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
                return;
            }
            Application.Run(new WorkerForm());
        }
    }
}

internal static class UiTheme
{
    public static readonly Color Background = Color.FromArgb(15, 23, 42);
    public static readonly Color Surface = Color.FromArgb(30, 41, 59);
    public static readonly Color SurfaceRaised = Color.FromArgb(51, 65, 85);
    public static readonly Color Text = Color.FromArgb(241, 245, 249);
    public static readonly Color Muted = Color.FromArgb(148, 163, 184);
    public static readonly Color Green = Color.FromArgb(74, 222, 128);
    public static readonly Color Amber = Color.FromArgb(251, 191, 36);
    public static readonly Color Red = Color.FromArgb(248, 113, 113);
    public static readonly Color Blue = Color.FromArgb(96, 165, 250);
}

internal sealed class WorkerForm : Form
{
    private const int RestartDelaySeconds = 5;

    private readonly string desktopPath;
    private readonly string workerRoot;
    private readonly string workerScript;
    private readonly string envFile;

    private Label statusDot;
    private Label statusValue;
    private Label statusHint;
    private Label connectionValue;
    private Label connectionHint;
    private Label stageValue;
    private Label stageHint;
    private Label recentJobValue;
    private Label recentJobHint;
    private Label restartValue;
    private Label restartHint;
    private TextBox logBox;
    private Button actionButton;
    private System.Windows.Forms.Timer restartTimer;
    private System.Windows.Forms.Timer uptimeTimer;
    private Process workerProcess;
    private DateTime workerStartedAt;
    private int restartCount;
    private bool closing;
    private bool manualStop;

    public WorkerForm()
    {
        desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        workerRoot = Path.Combine(
            desktopPath,
            "2\uD559\uAE30",
            "S15P11A204-deploy-ai-worker-env-fix",
            "ai-worker");
        workerScript = Path.Combine(workerRoot, "scripts", "Start-NotebookAiWorker.ps1");
        envFile = Path.Combine(desktopPath, "<worker-env-file>");

        Text = "EyesOnU AI Worker";
        StartPosition = FormStartPosition.Manual;
        Location = new Point(40, 40);
        MinimumSize = new Size(820, 600);
        Size = new Size(900, 650);
        BackColor = UiTheme.Background;
        ForeColor = UiTheme.Text;
        Font = new Font("Segoe UI", 10.0f);
        FormBorderStyle = FormBorderStyle.Sizable;
        DoubleBuffered = true;

        BuildUi();

        restartTimer = new System.Windows.Forms.Timer();
        restartTimer.Interval = RestartDelaySeconds * 1000;
        restartTimer.Tick += delegate
        {
            restartTimer.Stop();
            if (!closing && workerProcess == null)
            {
                StartWorker();
            }
        };

        uptimeTimer = new System.Windows.Forms.Timer();
        uptimeTimer.Interval = 1000;
        uptimeTimer.Tick += delegate { UpdateUptime(); };

        Shown += delegate { StartWorker(); };
        FormClosing += OnFormClosing;
    }

    private void BuildUi()
    {
        Panel body = new Panel();
        body.Dock = DockStyle.Fill;
        body.Padding = new Padding(24, 18, 24, 20);
        body.BackColor = UiTheme.Background;

        Panel header = new Panel();
        header.Dock = DockStyle.Fill;
        header.Height = 112;
        header.Padding = new Padding(24, 18, 24, 14);
        header.BackColor = UiTheme.Surface;

        Label title = new Label();
        title.AutoSize = true;
        title.Text = "EyesOnU AI Worker";
        title.Font = new Font("Segoe UI Semibold", 20.0f, FontStyle.Bold);
        title.ForeColor = UiTheme.Text;
        title.Location = new Point(24, 16);
        header.Controls.Add(title);

        Label subtitle = new Label();
        subtitle.AutoSize = false;
        subtitle.Width = header.Width - 52;
        subtitle.Height = 24;
        subtitle.Text = "\uBC31\uC5D4\uB4DC \uC791\uC5C5\uC744 \uAE30\uB2E4\uB9AC\uBA70 \uC2E4\uD328 \uC2DC \uC790\uB3D9 \uC7AC\uC2DC\uC791\uD569\uB2C8\uB2E4.";
        subtitle.Font = new Font("Segoe UI", 9.5f);
        subtitle.ForeColor = UiTheme.Muted;
        subtitle.Location = new Point(26, 52);
        header.Controls.Add(subtitle);

        statusDot = new Label();
        statusDot.AutoSize = true;
        statusDot.Text = "\u25CF";
        statusDot.Font = new Font("Segoe UI", 22.0f, FontStyle.Bold);
        statusDot.ForeColor = UiTheme.Amber;
        statusDot.Location = new Point(27, 72);
        header.Controls.Add(statusDot);

        statusValue = new Label();
        statusValue.AutoSize = true;
        statusValue.Text = "\uC2DC\uC791 \uC900\uBE44 \uC911";
        statusValue.Font = new Font("Segoe UI Semibold", 11.0f, FontStyle.Bold);
        statusValue.ForeColor = UiTheme.Text;
        statusValue.Location = new Point(58, 78);
        header.Controls.Add(statusValue);

        statusHint = new Label();
        statusHint.AutoSize = false;
        statusHint.Width = 330;
        statusHint.Height = 22;
        statusHint.Text = "\uBC31\uC5D4\uB4DC \uC694\uCCAD\uC744 \uAE30\uB2E4\uB9BD\uB2C8\uB2E4.";
        statusHint.Font = new Font("Segoe UI", 9.0f);
        statusHint.ForeColor = UiTheme.Muted;
        statusHint.Location = new Point(190, 80);
        header.Controls.Add(statusHint);

        actionButton = CreateButton("\uC6CC\uCEE4 \uC911\uC9C0", 150);
        actionButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        actionButton.Location = new Point(header.Width - actionButton.Width - 24, 30);
        actionButton.Click += OnActionButtonClick;
        header.Controls.Add(actionButton);
        header.Resize += delegate
        {
            actionButton.Left = header.ClientSize.Width - actionButton.Width - 24;
            subtitle.Width = Math.Max(160, actionButton.Left - subtitle.Left - 14);
            statusHint.Width = Math.Max(160, actionButton.Left - statusHint.Left - 14);
        };

        TableLayoutPanel metrics = new TableLayoutPanel();
        metrics.Dock = DockStyle.Top;
        metrics.Height = 184;
        metrics.ColumnCount = 2;
        metrics.RowCount = 2;
        metrics.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50.0f));
        metrics.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50.0f));
        metrics.RowStyles.Add(new RowStyle(SizeType.Percent, 50.0f));
        metrics.RowStyles.Add(new RowStyle(SizeType.Percent, 50.0f));
        metrics.Padding = new Padding(0, 0, 0, 12);

        Panel connectionCard = CreateMetricCard(
            "\uC5F0\uACB0 \uC0C1\uD0DC",
            "\uB300\uAE30 \uC911",
            "\uC911\uC559 \uC11C\uBC84\uC640 RabbitMQ \uC694\uCCAD \uB300\uAE30",
            out connectionValue,
            out connectionHint);
        Panel stageCard = CreateMetricCard(
            "\uD604\uC7AC \uB2E8\uACC4",
            "\uC2DC\uC791 \uC900\uBE44",
            "\uC218\uC2E0 \uB77C\uC778 \uC5D0\uC11C \uC0C1\uD0DC\uB97C \uC790\uB3D9 \uD45C\uC2DC",
            out stageValue,
            out stageHint);
        Panel recentCard = CreateMetricCard(
            "\uCD5C\uADFC \uC791\uC5C5",
            "\uC5C6\uC74C",
            "jobId \uBC0F \uC6CC\uCEE4 \uCC98\uB9AC \uC0C1\uD0DC",
            out recentJobValue,
            out recentJobHint);
        Panel restartCard = CreateMetricCard(
            "\uC790\uB3D9 \uC7AC\uC2DC\uC791",
            "0\uD68C",
            "\uC608\uC678 \uC885\uB8CC \uC2DC 5\uCD08 \uD6C4 \uC7AC\uC2DC\uC791",
            out restartValue,
            out restartHint);

        metrics.Controls.Add(connectionCard, 0, 0);
        metrics.Controls.Add(stageCard, 1, 0);
        metrics.Controls.Add(recentCard, 0, 1);
        metrics.Controls.Add(restartCard, 1, 1);

        Panel logPanel = new Panel();
        logPanel.Dock = DockStyle.Fill;
        logPanel.Padding = new Padding(0, 4, 0, 0);
        logPanel.BackColor = UiTheme.Background;

        Label logTitle = new Label();
        logTitle.Dock = DockStyle.Top;
        logTitle.Height = 28;
        logTitle.Text = "\uC2E4\uC2DC\uAC04 \uC6CC\uCEE4 \uB85C\uADF8";
        logTitle.Font = new Font("Segoe UI Semibold", 11.0f, FontStyle.Bold);
        logTitle.ForeColor = UiTheme.Text;

        logBox = new TextBox();
        logBox.Multiline = true;
        logBox.Dock = DockStyle.Fill;
        logBox.ReadOnly = true;
        logBox.BorderStyle = BorderStyle.None;
        logBox.BackColor = Color.FromArgb(2, 6, 23);
        logBox.ForeColor = Color.FromArgb(203, 213, 225);
        logBox.Font = new Font("Consolas", 9.0f);
        logBox.WordWrap = false;
        logBox.ScrollBars = ScrollBars.Vertical;
        logBox.TabStop = false;
        logPanel.Controls.Add(logBox);
        logPanel.Controls.Add(logTitle);

        Panel footer = new Panel();
        footer.Dock = DockStyle.Bottom;
        footer.Height = 48;
        footer.Padding = new Padding(0, 12, 0, 0);
        footer.BackColor = UiTheme.Background;

        Button openFolderButton = CreateButton("\uC6CC\uCEE4 \uD3F4\uB354 \uC5F4\uAE30", 150);
        openFolderButton.Dock = DockStyle.Left;
        openFolderButton.Click += delegate { OpenWorkerFolder(); };
        footer.Controls.Add(openFolderButton);

        Label pathLabel = new Label();
        pathLabel.AutoEllipsis = true;
        pathLabel.Dock = DockStyle.Fill;
        pathLabel.TextAlign = ContentAlignment.MiddleRight;
        pathLabel.ForeColor = UiTheme.Muted;
        pathLabel.Font = new Font("Segoe UI", 8.5f);
        pathLabel.Text = workerRoot;
        footer.Controls.Add(pathLabel);

        body.Controls.Add(logPanel);
        body.Controls.Add(metrics);
        body.Controls.Add(footer);

        TableLayoutPanel root = new TableLayoutPanel();
        root.Dock = DockStyle.Fill;
        root.ColumnCount = 1;
        root.RowCount = 2;
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 112.0f));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100.0f));
        root.Controls.Add(header, 0, 0);
        root.Controls.Add(body, 0, 1);
        Controls.Add(root);
        AppendLog("GUI \uC900\uBE44 \uC644\uB8CC. \uC6CC\uCEE4 \uC791\uC5C5\uC744 \uAE30\uB2E4\uB9BD\uB2C8\uB2E4.", false);
        AppendLog("\uB300\uAE30 \uD050: search.target.recording.queue", false);
    }

    private Button CreateButton(string text, int width)
    {
        Button button = new Button();
        button.Text = text;
        button.Width = width;
        button.Height = 34;
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderColor = UiTheme.SurfaceRaised;
        button.FlatAppearance.MouseOverBackColor = Color.FromArgb(71, 85, 105);
        button.BackColor = UiTheme.SurfaceRaised;
        button.ForeColor = UiTheme.Text;
        button.Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold);
        button.Cursor = Cursors.Hand;
        return button;
    }

    private Panel CreateMetricCard(
        string title,
        string value,
        string hint,
        out Label valueLabel,
        out Label hintLabel)
    {
        Panel card = new Panel();
        card.Dock = DockStyle.Fill;
        card.Margin = new Padding(0, 0, 12, 12);
        card.Padding = new Padding(16, 12, 16, 10);
        card.BackColor = UiTheme.Surface;
        card.BorderStyle = BorderStyle.FixedSingle;

        Label titleLabel = new Label();
        titleLabel.AutoSize = false;
        titleLabel.Text = title;
        titleLabel.ForeColor = UiTheme.Muted;
        titleLabel.Font = new Font("Segoe UI", 9.0f);

        hintLabel = new Label();
        hintLabel.AutoSize = false;
        hintLabel.Text = hint;
        hintLabel.ForeColor = UiTheme.Muted;
        hintLabel.Font = new Font("Segoe UI", 8.0f);
        hintLabel.AutoEllipsis = true;

        valueLabel = new Label();
        valueLabel.AutoSize = false;
        valueLabel.Text = value;
        valueLabel.ForeColor = UiTheme.Text;
        valueLabel.Font = new Font("Segoe UI Semibold", 12.5f, FontStyle.Bold);
        valueLabel.TextAlign = ContentAlignment.MiddleLeft;
        card.Controls.Add(titleLabel);
        card.Controls.Add(valueLabel);
        card.Controls.Add(hintLabel);
        Label layoutValueLabel = valueLabel;
        Label layoutHintLabel = hintLabel;
        Action layoutLabels = delegate
        {
            int left = card.Padding.Left;
            int top = card.Padding.Top;
            int width = Math.Max(1, card.ClientSize.Width - card.Padding.Left - card.Padding.Right);
            int hintHeight = 17;
            int titleHeight = 18;
            int valueHeight = Math.Max(20, card.ClientSize.Height - top - card.Padding.Bottom - titleHeight - hintHeight);
            titleLabel.SetBounds(left, top, width, titleHeight);
            layoutValueLabel.SetBounds(left, top + titleHeight, width, valueHeight);
            layoutHintLabel.SetBounds(left, card.ClientSize.Height - card.Padding.Bottom - hintHeight, width, hintHeight);
        };
        card.Resize += delegate { layoutLabels(); };
        layoutLabels();
        return card;
    }

    private ProcessStartInfo CreateWorkerStartInfo()
    {
        ProcessStartInfo info = new ProcessStartInfo();
        string powershell = Path.Combine(
            Environment.SystemDirectory,
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        info.FileName = Path.Combine(Environment.SystemDirectory, "cmd.exe");
        info.Arguments = string.Join(
            " ",
            "/d",
            "/c",
            powershell,
            "-NoProfile",
            "-ExecutionPolicy Bypass",
            "-File " + QuoteArgument(workerScript),
            "-EnvFile " + QuoteArgument(envFile),
            "-AuthMode worker",
            "-NoStatusWindow",
            "-LogLevel INFO");
        info.WorkingDirectory = workerRoot;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.RedirectStandardOutput = true;
        info.RedirectStandardError = true;
        info.StandardOutputEncoding = Encoding.UTF8;
        info.StandardErrorEncoding = Encoding.UTF8;
        info.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        return info;
    }

    private static string QuoteArgument(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private void StartWorker()
    {
        if (closing || workerProcess != null)
        {
            return;
        }

        if (!File.Exists(workerScript))
        {
            SetStatus(
                "\uC124\uC815 \uC624\uB958",
                "\uC2E4\uD589 \uC2A4\uD06C\uB9BD\uD2B8\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4.",
                UiTheme.Red);
            AppendLog("Missing worker script: " + workerScript, true);
            return;
        }
        if (!File.Exists(envFile))
        {
            SetStatus(
                "\uC124\uC815 \uC624\uB958",
                "<worker-env-file>\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4.",
                UiTheme.Red);
            AppendLog("Missing worker environment file: " + envFile, true);
            return;
        }

        restartTimer.Stop();
        manualStop = false;
        SetStatus(
            "\uC6CC\uCEE4 \uC2DC\uC791 \uC911",
            "\uC911\uC559 \uC11C\uBC84\uC640 \uC5F0\uACB0\uD558\uB294 \uC911\uC785\uB2C8\uB2E4.",
            UiTheme.Amber);
        stageValue.Text = "\uC2DC\uC791 \uC900\uBE44";
        connectionValue.Text = "\uC5F0\uACB0 \uC2DC\uB3C4";
        AppendLog("Starting notebook AI worker.", false);

        Process process = new Process();
        process.StartInfo = CreateWorkerStartInfo();
        process.EnableRaisingEvents = true;
        process.OutputDataReceived += OnWorkerOutput;
        process.ErrorDataReceived += OnWorkerError;
        process.Exited += OnWorkerExited;
        workerProcess = process;

        try
        {
            if (!process.Start())
            {
                throw new InvalidOperationException("PowerShell process did not start.");
            }
            workerStartedAt = DateTime.Now;
            uptimeTimer.Start();
            actionButton.Text = "\uC6CC\uCEE4 \uC911\uC9C0";
            SetStatus(
                "\uB300\uAE30 \uC911",
                "\uC6CC\uCEE4 \uD504\uB85C\uC138\uC2A4\uAC00 \uBC31\uC5D4\uB4DC \uC791\uC5C5\uC744 \uAE30\uB2E4\uB9BD\uB2C8\uB2E4.",
                UiTheme.Green);
            connectionValue.Text = "\uC2E4\uD589 \uC911";
            stageValue.Text = "RabbitMQ \uC791\uC5C5 \uB300\uAE30";
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
        }
        catch (Exception exception)
        {
            workerProcess = null;
            process.Dispose();
            HandleStartFailure(exception, process.StartInfo);
        }
    }

    private void StopWorker(bool fromUser)
    {
        manualStop = fromUser;
        restartTimer.Stop();
        uptimeTimer.Stop();
        Process process = workerProcess;
        if (process == null)
        {
            actionButton.Text = "\uC6CC\uCEE4 \uC2DC\uC791";
            SetStatus("\uC911\uC9C0\uB428", "\uC0AC\uC6A9\uC790\uAC00 \uC6CC\uCEE4\uB97C \uC911\uC9C0\uD588\uC2B5\uB2C8\uB2E4.", UiTheme.Muted);
            return;
        }

        AppendLog("Stopping notebook AI worker.", false);
        try
        {
            if (!process.HasExited)
            {
                KillProcessTree(process);
            }
        }
        catch (Exception exception)
        {
            AppendLog("Worker stop failed: " + exception.Message, true);
        }
    }

    private void OnActionButtonClick(object sender, EventArgs e)
    {
        if (workerProcess != null)
        {
            StopWorker(true);
        }
        else
        {
            StartWorker();
        }
    }

    private void OnWorkerOutput(object sender, DataReceivedEventArgs e)
    {
        QueueWorkerLine(e.Data, false);
    }

    private void OnWorkerError(object sender, DataReceivedEventArgs e)
    {
        QueueWorkerLine(e.Data, true);
    }

    private void QueueWorkerLine(string line, bool isError)
    {
        if (String.IsNullOrEmpty(line) || closing)
        {
            return;
        }
        try
        {
            BeginInvoke((MethodInvoker)delegate { ProcessWorkerLine(line, isError); });
        }
        catch (InvalidOperationException)
        {
            // The form is closing.
        }
    }

    private void ProcessWorkerLine(string line, bool streamError)
    {
        string safeLine = SanitizeLog(line);
        bool isError = IsActualError(line);
        AppendLog(safeLine, isError);

        string lower = line.ToLowerInvariant();
        Match jobMatch = Regex.Match(line, @"(?i)job[_ -]?id[=: ]+([A-Za-z0-9-]+)");
        if (jobMatch.Success)
        {
            recentJobValue.Text = jobMatch.Groups[1].Value;
            recentJobHint.Text = "\uB9C8\uC9C0\uB9C9 \uC791\uC5C5 \uC2DC\uAC04 " + DateTime.Now.ToString("HH:mm:ss");
        }

        if (isError)
        {
            SetStatus("\uC624\uB958 \uAC10\uC9C0", "\uC0C1\uC138 \uB85C\uADF8\uB97C \uD655\uC778\uD558\uC138\uC694.", UiTheme.Red);
            stageValue.Text = "\uC624\uB958 \uD655\uC778";
        }
        else if (lower.Contains("complete") || lower.Contains("result"))
        {
            SetStatus("\uACB0\uACFC \uC804\uC1A1 \uC644\uB8CC", "\uB2E4\uC74C \uBC31\uC5D4\uB4DC \uC791\uC5C5\uC744 \uAE30\uB2E4\uB9BD\uB2C8\uB2E4.", UiTheme.Green);
            stageValue.Text = "\uACB0\uACFC \uC804\uC1A1";
        }
        else if (lower.Contains("infer") || lower.Contains("\uCD94\uB860"))
        {
            SetStatus("\uC791\uC5C5 \uCC98\uB9AC \uC911", "\uC2E4\uC81C AI \uCD94\uB860\uC774 \uC9C4\uD589 \uC911\uC785\uB2C8\uB2E4.", UiTheme.Blue);
            stageValue.Text = "AI \uCD94\uB860";
        }
        else if (lower.Contains("download") || lower.Contains("\uB2E4\uC6B4\uB85C\uB4DC"))
        {
            SetStatus("\uC791\uC5C5 \uCC98\uB9AC \uC911", "\uB300\uC0C1 \uC601\uC0C1\uC744 \uC900\uBE44\uD558\uB294 \uC911\uC785\uB2C8\uB2E4.", UiTheme.Blue);
            stageValue.Text = "\uC601\uC0C1 \uB2E4\uC6B4\uB85C\uB4DC";
        }
        else if (lower.Contains("claim") || lower.Contains("\uC18C\uC720\uAD8C"))
        {
            SetStatus("\uC791\uC5C5 \uCC98\uB9AC \uC911", "\uBC31\uC5D4\uB4DC \uC791\uC5C5\uC744 \uD655\uBCF4\uD588\uC2B5\uB2C8\uB2E4.", UiTheme.Blue);
            stageValue.Text = "\uC791\uC5C5 \uD655\uBCF4";
        }
        else if (lower.Contains("wait") || lower.Contains("rabbit") || lower.Contains("consume"))
        {
            SetStatus("\uB300\uAE30 \uC911", "RabbitMQ\uC5D0\uC11C \uC0C8 \uC791\uC5C5\uC744 \uAE30\uB2E4\uB9BD\uB2C8\uB2E4.", UiTheme.Green);
            stageValue.Text = "\uBC31\uC5D4\uB4DC \uC791\uC5C5 \uB300\uAE30";
            connectionValue.Text = "\uC5F0\uACB0\uB428";
        }
    }

    private static bool IsActualError(string line)
    {
        if (String.IsNullOrWhiteSpace(line))
        {
            return false;
        }
        string lower = line.ToLowerInvariant();
        return Regex.IsMatch(line, @"(?i)\b(critical|error|traceback|exception)\b")
            || lower.Contains("central completion was not confirmed")
            || lower.Contains("worker lease was lost")
            || lower.Contains("worker launch failed");
    }

    private void OnWorkerExited(object sender, EventArgs e)
    {
        Process process = (Process)sender;
        int exitCode = -1;
        try
        {
            process.WaitForExit();
            exitCode = process.ExitCode;
        }
        catch (Exception exception)
        {
            AppendLog("Worker exit inspection failed: " + exception.Message, true);
        }

        try
        {
            BeginInvoke((MethodInvoker)delegate { FinishWorker(process, exitCode); });
        }
        catch (InvalidOperationException)
        {
            // The form is closing.
        }
    }

    private void FinishWorker(Process process, int exitCode)
    {
        if (workerProcess != process)
        {
            process.Dispose();
            return;
        }

        workerProcess = null;
        uptimeTimer.Stop();
        AppendLog("Worker exited with code " + exitCode + ".", exitCode != 0);
        actionButton.Text = "\uC6CC\uCEE4 \uC2DC\uC791";

        if (closing)
        {
            process.Dispose();
            return;
        }
        if (manualStop)
        {
            manualStop = false;
            SetStatus("\uC911\uC9C0\uB428", "\uC0AC\uC6A9\uC790\uAC00 \uC6CC\uCEE4\uB97C \uC911\uC9C0\uD588\uC2B5\uB2C8\uB2E4.", UiTheme.Muted);
            connectionValue.Text = "\uC911\uC9C0\uB428";
        }
        else
        {
            restartCount++;
            restartValue.Text = restartCount + "\uD68C";
            restartHint.Text = "\uC608\uC678 \uC885\uB8CC \uD6C4 " + RestartDelaySeconds + "\uCD08 \uB4A4 \uC790\uB3D9 \uC7AC\uC2DC\uC791";
            SetStatus(
                "\uC7AC\uC2DC\uC791 \uB300\uAE30",
                RestartDelaySeconds + "\uCD08 \uD6C4 \uC6CC\uCEE4\uB97C \uB2E4\uC2DC \uC2DC\uC791\uD569\uB2C8\uB2E4.",
                UiTheme.Amber);
            connectionValue.Text = "\uC7AC\uC2DC\uC791 \uB300\uAE30";
            restartTimer.Start();
        }
        process.Dispose();
    }

    private void ScheduleRestart()
    {
        if (closing)
        {
            return;
        }
        restartCount++;
        restartValue.Text = restartCount + "\uD68C";
        SetStatus(
            "\uC7AC\uC2DC\uC791 \uB300\uAE30",
            RestartDelaySeconds + "\uCD08 \uD6C4 \uC6CC\uCEE4\uB97C \uB2E4\uC2DC \uC2DC\uC791\uD569\uB2C8\uB2E4.",
            UiTheme.Amber);
        restartTimer.Start();
    }

    private void HandleStartFailure(Exception exception, ProcessStartInfo startInfo)
    {
        string nativeCode = "";
        System.ComponentModel.Win32Exception win32 = exception as System.ComponentModel.Win32Exception;
        if (win32 != null)
        {
            nativeCode = " NativeErrorCode=" + win32.NativeErrorCode;
        }
        string diagnostic =
            "Worker launch failed: "
            + exception.GetType().FullName
            + " HResult=" + exception.HResult
            + nativeCode
            + " Message=" + exception.Message;
        AppendLog(
            diagnostic,
            true);
        try
        {
            File.AppendAllText(
                Path.Combine(Path.GetTempPath(), "EyesOnU-AI-Worker-launch.log"),
                DateTime.Now.ToString("o") + Environment.NewLine
                + diagnostic + Environment.NewLine
                + "FileName=" + startInfo.FileName + Environment.NewLine
                + "WorkingDirectory=" + startInfo.WorkingDirectory + Environment.NewLine
                + "Arguments=" + startInfo.Arguments + Environment.NewLine
                + Environment.NewLine,
                Encoding.UTF8);
        }
        catch (Exception logException)
        {
            AppendLog("Could not write launch diagnostic: " + logException.Message, true);
        }
        SetStatus("\uC2DC\uC791 \uC2E4\uD328", "\uC624\uB958 \uD6C4 \uC790\uB3D9 \uC7AC\uC2DC\uC791\uC744 \uC2DC\uB3C4\uD569\uB2C8\uB2E4.", UiTheme.Red);
        connectionValue.Text = "\uC2DC\uC791 \uC2E4\uD328";
        ScheduleRestart();
    }

    private void SetStatus(string title, string hint, Color color)
    {
        statusDot.ForeColor = color;
        statusValue.Text = title;
        statusHint.Text = hint;
    }

    private void AppendLog(string line, bool isError)
    {
        if (logBox == null || closing)
        {
            return;
        }
        string prefix = DateTime.Now.ToString("HH:mm:ss") + "  ";
        string level = isError ? "[ERROR] " : String.Empty;
        logBox.AppendText(prefix + level + line + Environment.NewLine);
        if (logBox.TextLength > 70000)
        {
            logBox.Select(0, 12000);
            logBox.SelectedText = String.Empty;
        }
        logBox.SelectionStart = logBox.TextLength;
        logBox.ScrollToCaret();
    }

    private static string SanitizeLog(string line)
    {
        string sanitized = line.Replace("\r", String.Empty).Replace("\n", String.Empty);
        sanitized = Regex.Replace(
            sanitized,
            @"(?i)(x-worker-key|authorization|password|secret|token)(\s*[:=]\s*)\S+",
            "$1$2[REDACTED]");
        sanitized = Regex.Replace(
            sanitized,
            @"(?i)(X-Amz-(?:Signature|Credential|Security-Token)=)[^&\s]+",
            "$1[REDACTED]");
        if (sanitized.Length > 900)
        {
            sanitized = sanitized.Substring(0, 900) + " ...";
        }
        return sanitized;
    }

    private void UpdateUptime()
    {
        if (workerProcess == null)
        {
            return;
        }
        TimeSpan elapsed = DateTime.Now - workerStartedAt;
        connectionHint.Text = "\uC2E4\uD589 \uC2DC\uAC04 " + elapsed.ToString(@"hh\:mm\:ss");
    }

    private void OpenWorkerFolder()
    {
        try
        {
            Process.Start("explorer.exe", QuoteArgument(workerRoot));
        }
        catch (Exception exception)
        {
            AppendLog("Could not open worker folder: " + exception.Message, true);
        }
    }

    private static void KillProcessTree(Process process)
    {
        ProcessStartInfo killInfo = new ProcessStartInfo();
        killInfo.FileName = Path.Combine(Environment.SystemDirectory, "taskkill.exe");
        killInfo.Arguments = "/PID " + process.Id + " /T /F";
        killInfo.UseShellExecute = false;
        killInfo.CreateNoWindow = true;
        killInfo.RedirectStandardOutput = true;
        killInfo.RedirectStandardError = true;
        using (Process killer = Process.Start(killInfo))
        {
            if (killer == null || !killer.WaitForExit(10000))
            {
                throw new InvalidOperationException("Worker process tree did not stop in time.");
            }
        }
        if (!process.HasExited)
        {
            throw new InvalidOperationException("Worker process tree is still running.");
        }
    }

    private void OnFormClosing(object sender, FormClosingEventArgs e)
    {
        closing = true;
        restartTimer.Stop();
        uptimeTimer.Stop();
        Process process = workerProcess;
        workerProcess = null;
        if (process != null)
        {
            try
            {
                if (!process.HasExited)
                {
                    KillProcessTree(process);
                }
            }
            catch (Exception exception)
            {
                AppendLog("Worker shutdown warning: " + exception.Message, true);
            }
            process.Dispose();
        }
    }
}
'@

$addTypeParams = @{
    TypeDefinition = $source
    Language = "CSharp"
    ReferencedAssemblies = @("System.dll", "System.Core.dll", "System.Drawing.dll", "System.Windows.Forms.dll")
    OutputAssembly = $OutputPath
    OutputType = "WindowsApplication"
}
Add-Type @addTypeParams

Write-Output "Built: $OutputPath"

