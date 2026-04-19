using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Principal;
using System.Windows.Forms;
using Microsoft.Win32;

namespace CorelDRAWAutomationToolkitInstaller
{
    internal static class Program
    {
        private const string AppName = "CorelDRAW Automation Toolkit";
        private const string AppVersion = "1.0.0";
        private const string ExeName = "CorelDRAW_Automation_Toolkit.exe";
        private const string ProductKey = @"Software\CorelDRAW Automation Toolkit";
        private const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit";

        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            if (args.Length > 0 && string.Equals(args[0], "/uninstall", StringComparison.OrdinalIgnoreCase))
            {
                if (!EnsureElevated(args))
                {
                    return 0;
                }

                Uninstall();
                return 0;
            }

            if (!EnsureElevated(args))
            {
                return 0;
            }

            Install();
            return 0;
        }

        private static bool EnsureElevated(string[] args)
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                if (principal.IsInRole(WindowsBuiltInRole.Administrator))
                {
                    return true;
                }
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = Application.ExecutablePath,
                    Arguments = string.Join(" ", args),
                    UseShellExecute = true,
                    Verb = "runas"
                };
                Process.Start(psi);
            }
            catch
            {
                MessageBox.Show(
                    "Administrator approval is required to install this application.",
                    AppName,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
            }

            return false;
        }

        private static string InstallDir
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppName);
            }
        }

        private static string StartMenuDir
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), AppName);
            }
        }

        private static string DesktopShortcut
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), AppName + ".lnk");
            }
        }

        private static void Install()
        {
            string installDir = InstallDir;
            Directory.CreateDirectory(installDir);

            ExtractResource("AppPayload.exe", Path.Combine(installDir, ExeName));
            File.Copy(Application.ExecutablePath, Path.Combine(installDir, "uninstall.exe"), true);
            ExtractOptionalResource("LicenseText", Path.Combine(installDir, "LICENSE.txt"));

            Directory.CreateDirectory(StartMenuDir);
            CreateShortcut(Path.Combine(StartMenuDir, AppName + ".lnk"), Path.Combine(installDir, ExeName), installDir, AppName);
            CreateShortcut(Path.Combine(StartMenuDir, "Uninstall.lnk"), Path.Combine(installDir, "uninstall.exe"), installDir, "Uninstall " + AppName, "/uninstall");
            CreateShortcut(DesktopShortcut, Path.Combine(installDir, ExeName), installDir, AppName);

            using (RegistryKey product = Registry.LocalMachine.CreateSubKey(ProductKey))
            {
                if (product != null)
                {
                    product.SetValue("InstallPath", installDir, RegistryValueKind.String);
                }
            }

            using (RegistryKey uninstall = Registry.LocalMachine.CreateSubKey(UninstallKey))
            {
                if (uninstall != null)
                {
                    uninstall.SetValue("DisplayName", AppName, RegistryValueKind.String);
                    uninstall.SetValue("DisplayVersion", AppVersion, RegistryValueKind.String);
                    uninstall.SetValue("Publisher", "CorelDRAW Automation Team", RegistryValueKind.String);
                    uninstall.SetValue("InstallLocation", installDir, RegistryValueKind.String);
                    uninstall.SetValue("DisplayIcon", Path.Combine(installDir, ExeName), RegistryValueKind.String);
                    uninstall.SetValue("UninstallString", "\"" + Path.Combine(installDir, "uninstall.exe") + "\" /uninstall", RegistryValueKind.String);
                    uninstall.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    uninstall.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                }
            }

            DialogResult launchNow = MessageBox.Show(
                "Installation complete.\n\nDesktop and Start Menu shortcuts were created.\n\nLaunch now?",
                AppName,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information);

            if (launchNow == DialogResult.Yes)
            {
                Process.Start(Path.Combine(installDir, ExeName));
            }
        }

        private static void Uninstall()
        {
            string installDir = InstallDir;

            try
            {
                if (File.Exists(DesktopShortcut))
                {
                    File.Delete(DesktopShortcut);
                }

                if (Directory.Exists(StartMenuDir))
                {
                    Directory.Delete(StartMenuDir, true);
                }
            }
            catch
            {
            }

            try
            {
                Registry.LocalMachine.DeleteSubKeyTree(UninstallKey, false);
            }
            catch
            {
            }

            try
            {
                Registry.LocalMachine.DeleteSubKeyTree(ProductKey, false);
            }
            catch
            {
            }

            try
            {
                if (Directory.Exists(installDir))
                {
                    Directory.Delete(installDir, true);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Could not remove all installed files.\n\n" + ex.Message,
                    AppName,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return;
            }

            MessageBox.Show(
                "Uninstallation complete.",
                AppName,
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
        }

        private static void ExtractResource(string resourceName, string outputPath)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (stream == null)
                {
                    throw new InvalidOperationException("Missing embedded resource: " + resourceName);
                }

                using (FileStream file = new FileStream(outputPath, FileMode.Create, FileAccess.Write))
                {
                    stream.CopyTo(file);
                }
            }
        }

        private static void ExtractOptionalResource(string resourceName, string outputPath)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (stream == null)
                {
                    return;
                }

                using (FileStream file = new FileStream(outputPath, FileMode.Create, FileAccess.Write))
                {
                    stream.CopyTo(file);
                }
            }
        }

        private static void CreateShortcut(string shortcutPath, string targetPath, string workingDirectory, string description, string arguments = null)
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            dynamic shell = Activator.CreateInstance(shellType);
            dynamic shortcut = shell.CreateShortcut(shortcutPath);
            shortcut.TargetPath = targetPath;
            shortcut.WorkingDirectory = workingDirectory;
            shortcut.Description = description;
            if (!string.IsNullOrWhiteSpace(arguments))
            {
                shortcut.Arguments = arguments;
            }
            shortcut.Save();
        }
    }
}
