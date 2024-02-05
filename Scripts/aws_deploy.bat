@echo off
cd ..

echo Installing Requests to Zip...
pip install requests -t aws_deploy

echo Copying Files to Zip...
copy aws_lambda.py aws_deploy
copy Spotify.py aws_deploy

echo|set /p="Creating Zip File..."
cd aws_deploy
tar --exclude="bin" --exclude="*.dist-info" -acf ../lambda_code.zip *
cd ..
echo File Created!

echo|set /p="Uploading to AWS..."
aws lambda update-function-code --function-name SpotifyMashup --zip-file fileb://lambda_code.zip > aws_deploy_results.json
echo File Uploaded!

echo|set /p="Removing Directories..."
rmdir /s /q aws_deploy
del lambda_code.zip
echo Finished!
