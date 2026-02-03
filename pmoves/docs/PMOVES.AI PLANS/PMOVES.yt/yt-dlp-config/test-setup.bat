# Example download commands to test the setup

echo "Testing yt-dlp configuration..."
echo.

echo "1. Testing with a short YouTube video (information only):"
yt-dlp --config-location "C:\Users\russe\yt-dlp-config\config.txt" --simulate --print "File would be: %(title)s.%(ext)s" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

echo.
echo "2. Testing PowerShell module import:"
powershell -Command "Import-Module 'C:\Users\russe\yt-dlp-config\yt-dlp-config.psm1'; Write-Host 'PowerShell module imported successfully!'"

echo.
echo "3. Testing batch script:"
call "C:\Users\russe\yt-dlp-config\yt-dlp-quick.bat"

echo.
echo "Configuration test completed!"