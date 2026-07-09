using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

public static class MentalOmegaRandomizerLauncher
{
    [STAThread]
    public static void Main()
    {
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string script = Path.Combine(exeDir, "RandomizerLauncher", "launcher_gui.py");
        if (!File.Exists(script))
        {
            script = Path.Combine(exeDir, "launcher_gui.py");
        }

        if (!File.Exists(script))
        {
            MessageBox.Show("Could not find RandomizerLauncher\\launcher_gui.py.", "Mental Omega Randomizer");
            return;
        }

        string[,] candidates = new string[,]
        {
            { "pyw.exe", "-3 \"" + script + "\"" },
            { "py.exe", "-3 \"" + script + "\"" },
            { "pythonw.exe", "\"" + script + "\"" },
            { "python.exe", "\"" + script + "\"" }
        };
        for (int index = 0; index < candidates.GetLength(0); index++)
        {
            try
            {
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = candidates[index, 0];
                info.Arguments = candidates[index, 1];
                info.WorkingDirectory = Path.GetDirectoryName(script);
                info.UseShellExecute = false;
                Process.Start(info);
                return;
            }
            catch
            {
                // Try the next Python launcher candidate.
            }
        }

        MessageBox.Show("Python was not found. Install Python or run RandomizerLauncher\\launcher_gui.py directly.", "Mental Omega Randomizer");
    }
}
