using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

internal static class Program
{
    private static int Main()
    {
        string destination = Path.Combine(Path.GetTempPath(), "RAMBLA-Premontato-Setup-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(destination);
            ExtractPayload(destination);
            string script = Path.Combine(destination, "install", "Install-Premontato.ps1");
            string pluginRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "Blackmagic Design", "DaVinci Resolve", "Support", "Workflow Integration Plugins");
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = "powershell.exe";
            start.Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + Quote(script) + " -PluginRoot " + Quote(pluginRoot);
            start.UseShellExecute = true;
            start.Verb = "runas";
            using (Process process = Process.Start(start))
            {
                if (process == null) throw new InvalidOperationException("Impossibile avviare l'installazione.");
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "RAMBLA Premontato Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        finally
        {
            try { if (Directory.Exists(destination)) Directory.Delete(destination, true); }
            catch { }
        }
    }

    private static void ExtractPayload(string destination)
    {
        Assembly assembly = Assembly.GetExecutingAssembly();
        using (Stream resource = assembly.GetManifestResourceStream("Premontato.payload.zip"))
        {
            if (resource == null) throw new InvalidOperationException("Payload installer non trovato.");
            using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read))
            {
                string root = Path.GetFullPath(destination) + Path.DirectorySeparatorChar;
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
                    string path = Path.GetFullPath(Path.Combine(destination, relative));
                    if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("Percorso non consentito nel payload.");
                    if (entry.FullName.EndsWith("/", StringComparison.Ordinal) || entry.FullName.EndsWith("\\", StringComparison.Ordinal))
                    {
                        Directory.CreateDirectory(path);
                        continue;
                    }
                    string parent = Path.GetDirectoryName(path);
                    if (!Directory.Exists(parent)) Directory.CreateDirectory(parent);
                    using (Stream input = entry.Open())
                    using (FileStream output = File.Create(path)) input.CopyTo(output);
                }
            }
        }
    }

    private static string Quote(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }
}
