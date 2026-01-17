// Created by Gneiss64 at https://github.com/Gneiss64/DBFZRaidEnabler
// This code is unused, but kept for reference. Specifically, the pattern scanning and patching logic for patcher.py
using System;
using System.IO;
using System.Globalization;

namespace DBFZRaidEnabler
{
    internal class Program
    {
        static void Main(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine("Patches DBFZ to enable raids locally.");
                Console.WriteLine("Usage: DBFZRaidEnabler <EXE> <RAID>");
                Console.WriteLine("EXE is the path of the game executable (RED-Win64-Shipping.exe).");
                Console.WriteLine("RAID is the index of the raid to enable. Must be greater than 0.");
            }
            else
            {
                byte[] exe = File.ReadAllBytes(args[0]);
                byte[] raidIndex = BitConverter.GetBytes(int.Parse(args[1]));
                byte[] getAsm = {0xB8, 0xDE, 0xAD, 0xBE, 0xEF, 0x90};
                Buffer.BlockCopy(raidIndex, 0x00, getAsm, 0x01, raidIndex.Length);
                int getOffset = ReplacePattern(exe, "8B 81 C4 53 1D 00", getAsm);
                if (getOffset < 0)
                {
                    Console.WriteLine("Get raid pattern scan failed.");
                    return;
                }
                byte[] setAsm = {0x41, 0xC7, 0x40, 0x04, 0xDE, 0xAD, 0xBE, 0xEF, 0x90, 0x90, 0x90};
                Buffer.BlockCopy(raidIndex, 0x00, setAsm, 0x04, raidIndex.Length);
                int setOffset = ReplacePattern(exe, "66 0F 73 DA 08 66 41 0F 7E 50 04 F2 0F 11 4C", setAsm);
                if (setOffset < 0)
                {
                    Console.WriteLine("Set raid pattern scan failed.");
                    return;
                }
                byte[] statusAsm = {0x39, 0xC0, 0x90, 0x90};
                int statusOffset = ReplacePattern(exe, "83 78 10 02 74 10", statusAsm);
                if (statusOffset < 0)
                {
                    Console.WriteLine("Raid status pattern scan failed.");
                    return;
                }
                File.WriteAllBytes(args[0], exe);
                Console.WriteLine("The executable was patched successfully.");
                Console.WriteLine($"Get raid: {getOffset:X}");
                Console.WriteLine($"Set raid: {setOffset:X}");
                Console.WriteLine($"Raid status: {statusOffset:X}");
            }
        }
        static int ReplacePattern(byte[] exe, string pattern, byte[] newBytes)
        {
            string[] bytes = pattern.Split(' ');
            for (int i = 0; i < exe.Length - bytes.Length; i++)
            {
                bool found = true;
                for (int j = 0; j < bytes.Length; j++)
                {
                    found &= bytes[j] == "??" || byte.Parse(bytes[j], NumberStyles.HexNumber) == exe[i + j];
                }
                if (found)
                {
                    newBytes.CopyTo(exe, i);
                    return i;
                }
            }
            return -1;
        }
    }
}