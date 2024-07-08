# server for version 2

### Start

python server/main.py

### Configurations

pip install -r requirements.txt 

### Intro

Made using FastAPI with a Mongo connection. Most functions are async, with an emphasis on non-blocking calls

### Tips

1. Find docs: http://localhost/docs
2. Testing suite: pytest tests/*test.py*

### First time pulling 
1. ``` pip install black ```

2. ``` pip install flake8 ```

3. ``` pip install pre-commit ```

4. ``` pre-commit run --all-files ```

Then make the necessary changes to the files. When you commit the file black will automatically format your code, flake8 may give you semantical errors. Manually debug, then add and commit again and then push.

### Contributing

PLEASE MAKE A BRANCH 
