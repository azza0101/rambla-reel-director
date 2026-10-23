using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;

var resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("Premontato.payload.zip")
    ?? throw new InvalidOperationException("Payload installer non trovato.");
var destination = Path.Combine(Path.GetTempPath(), "RAMBLA-Premontato-Setup-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(destination);
try
{
    using (resource)
    using (var archive = new ZipArchive(resource, ZipArchiveMode.Read))
    {
        var root = Path.GetFullPath(destination) + Path.DirectorySeparatorChar;
        foreach (var entry in archive.Entries)
        {
            var path = Path.GetFullPath(Path.Combine(destination, entry.FullName));
            if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Percorso non consentito nel payload.");
            if (entry.FullName.EndsWith('/')) { Directory.CreateDirectory(path); continue; }
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            entry.ExtractToFile(path, overwrite: true);
        }
    }
    var script = Path.Combine(destination, "install", "Install-Premontato.ps1");
    var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = true, Verb = "runas" };
    start.ArgumentList.Add("-NoProfile");
    start.ArgumentList.Add("-ExecutionPolicy"); start.ArgumentList.Add("Bypass");
    start.ArgumentList.Add("-File"); start.ArgumentList.Add(script);
    start.ArgumentList.Add("-PluginRoot");
    start.ArgumentList.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Blackmagic Design", "DaVinci Resolve", "Support", "Workflow Integration Plugins"));
    using var process = Process.Start(start) ?? throw new InvalidOperationException("Impossibile avviare l'installazione.");
    process.WaitForExit();
    if (process.ExitCode != 0) Environment.ExitCode = process.ExitCode;
}
finally
{
    try { Directory.Delete(destination, recursive: true); } catch { }
}
