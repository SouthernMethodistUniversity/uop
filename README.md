# uop
UPF Optimal Placer 

# Setup Guide

## 0) Install Python 3

### Ubuntu/Debian
```sh
sudo apt install python3-venv
```

### Mac
```sh
brew install python
```

## 1) Virtual Environment

### Create a virtual environment
```sh
python3 -m venv uopc_virtual_env
```

## 2) Activate your virtual environment

### Linux/Mac
```sh
source uopc_virtual_env/bin/activate
```

Example:
```sh
$ source uopc_virtual_env/bin/activate
(uopc_virtual_env) $
```

### Deactivate virtual environment
```sh
deactivate
```

Example:
```sh
(uopc_virtual_env) $ deactivate
```

## 3) Install dependencies

### Install dependencies from `requirements.txt`
```sh
pip install -r requirements.txt
```

Example:
```sh
$ source uopc_virtual_env/bin/activate
(uopc_virtual_env) $ cat requirements.txt
colorlog
fastapi
folium
haversine
numpy
openpyxl
pandas
tabulate
uvicorn

(uopc_virtual_env) $ pip install -r requirements.txt
```

This will install the following dependencies:
- `colorlog`
- `fastapi`
- `folium`
- `haversine`
- `numpy`
- `openpyxl`
- `pandas`
- `tabulate`
- `uvicorn`

Typical output:
```sh
$ source uopc_virtual_env/bin/activate
(uopc_virtual_env) $ cat requirements.txt
colorlog
fastapi
folium
haversine
numpy
openpyxl
pandas
tabulate
uvicorn

(uopc_virtual_env) $ pip install -r requirements.txt
Collecting colorlog (from -r requirements.txt (line 1))
  Using cached colorlog-6.9.0-py3-none-any.whl.metadata (10 kB)
Collecting fastapi (from -r requirements.txt (line 2))
  Downloading fastapi-0.115.11-py3-none-any.whl.metadata (27 kB)
Collecting folium (from -r requirements.txt (line 3))
  Downloading folium-0.19.5-py2.py3-none-any.whl.metadata (4.1 kB)
Collecting haversine (from -r requirements.txt (line 4))
  Using cached haversine-2.9.0-py2.py3-none-any.whl.metadata (5.8 kB)
Collecting numpy (from -r requirements.txt (line 5))
  Downloading numpy-2.2.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (62 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 62.0/62.0 kB 4.6 MB/s eta 0:00:00
Collecting openpyxl (from -r requirements.txt (line 6))
  Using cached openpyxl-3.1.5-py2.py3-none-any.whl.metadata (2.5 kB)
Collecting pandas (from -r requirements.txt (line 7))
  Using cached pandas-2.2.3-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (89 kB)
Collecting tabulate (from -r requirements.txt (line 8))
  Using cached tabulate-0.9.0-py3-none-any.whl.metadata (34 kB)
Collecting uvicorn (from -r requirements.txt (line 9))
  Using cached uvicorn-0.34.0-py3-none-any.whl.metadata (6.5 kB)
Collecting starlette<0.47.0,>=0.40.0 (from fastapi->-r requirements.txt (line 2))
  Downloading starlette-0.46.1-py3-none-any.whl.metadata (6.2 kB)
Collecting pydantic!=1.8,!=1.8.1,!=2.0.0,!=2.0.1,!=2.1.0,<3.0.0,>=1.7.4 (from fastapi->-r requirements.txt (line 2))
  Using cached pydantic-2.10.6-py3-none-any.whl.metadata (30 kB)
Collecting typing-extensions>=4.8.0 (from fastapi->-r requirements.txt (line 2))
  Using cached typing_extensions-4.12.2-py3-none-any.whl.metadata (3.0 kB)
Collecting branca>=0.6.0 (from folium->-r requirements.txt (line 3))
  Using cached branca-0.8.1-py3-none-any.whl.metadata (1.5 kB)
Collecting jinja2>=2.9 (from folium->-r requirements.txt (line 3))
  Downloading jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting requests (from folium->-r requirements.txt (line 3))
  Using cached requests-2.32.3-py3-none-any.whl.metadata (4.6 kB)
Collecting xyzservices (from folium->-r requirements.txt (line 3))
  Using cached xyzservices-2025.1.0-py3-none-any.whl.metadata (4.3 kB)
Collecting et-xmlfile (from openpyxl->-r requirements.txt (line 6))
  Using cached et_xmlfile-2.0.0-py3-none-any.whl.metadata (2.7 kB)
Collecting python-dateutil>=2.8.2 (from pandas->-r requirements.txt (line 7))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting pytz>=2020.1 (from pandas->-r requirements.txt (line 7))
  Using cached pytz-2025.1-py2.py3-none-any.whl.metadata (22 kB)
Collecting tzdata>=2022.7 (from pandas->-r requirements.txt (line 7))
  Using cached tzdata-2025.1-py2.py3-none-any.whl.metadata (1.4 kB)
Collecting click>=7.0 (from uvicorn->-r requirements.txt (line 9))
  Using cached click-8.1.8-py3-none-any.whl.metadata (2.3 kB)
Collecting h11>=0.8 (from uvicorn->-r requirements.txt (line 9))
  Using cached h11-0.14.0-py3-none-any.whl.metadata (8.2 kB)
Collecting MarkupSafe>=2.0 (from jinja2>=2.9->folium->-r requirements.txt (line 3))
  Using cached MarkupSafe-3.0.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.0 kB)
Collecting annotated-types>=0.6.0 (from pydantic!=1.8,!=1.8.1,!=2.0.0,!=2.0.1,!=2.1.0,<3.0.0,>=1.7.4->fastapi->-r requirements.txt (line 2))
  Using cached annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.27.2 (from pydantic!=1.8,!=1.8.1,!=2.0.0,!=2.0.1,!=2.1.0,<3.0.0,>=1.7.4->fastapi->-r requirements.txt (line 2))
  Using cached pydantic_core-2.27.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
Collecting six>=1.5 (from python-dateutil>=2.8.2->pandas->-r requirements.txt (line 7))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting anyio<5,>=3.6.2 (from starlette<0.47.0,>=0.40.0->fastapi->-r requirements.txt (line 2))
  Downloading anyio-4.9.0-py3-none-any.whl.metadata (4.7 kB)
Collecting charset-normalizer<4,>=2 (from requests->folium->-r requirements.txt (line 3))
  Using cached charset_normalizer-3.4.1-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (35 kB)
Collecting idna<4,>=2.5 (from requests->folium->-r requirements.txt (line 3))
  Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
Collecting urllib3<3,>=1.21.1 (from requests->folium->-r requirements.txt (line 3))
  Using cached urllib3-2.3.0-py3-none-any.whl.metadata (6.5 kB)
Collecting certifi>=2017.4.17 (from requests->folium->-r requirements.txt (line 3))
  Using cached certifi-2025.1.31-py3-none-any.whl.metadata (2.5 kB)
Collecting sniffio>=1.1 (from anyio<5,>=3.6.2->starlette<0.47.0,>=0.40.0->fastapi->-r requirements.txt (line 2))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Using cached colorlog-6.9.0-py3-none-any.whl (11 kB)
Downloading fastapi-0.115.11-py3-none-any.whl (94 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 94.9/94.9 kB 3.7 MB/s eta 0:00:00
Downloading folium-0.19.5-py2.py3-none-any.whl (110 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 110.9/110.9 kB 9.0 MB/s eta 0:00:00
Using cached haversine-2.9.0-py2.py3-none-any.whl (7.7 kB)
Downloading numpy-2.2.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (16.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 16.1/16.1 MB 20.5 MB/s eta 0:00:00
Using cached openpyxl-3.1.5-py2.py3-none-any.whl (250 kB)
Using cached pandas-2.2.3-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (12.7 MB)
Using cached tabulate-0.9.0-py3-none-any.whl (35 kB)
Using cached uvicorn-0.34.0-py3-none-any.whl (62 kB)
Using cached branca-0.8.1-py3-none-any.whl (26 kB)
Using cached click-8.1.8-py3-none-any.whl (98 kB)
Using cached h11-0.14.0-py3-none-any.whl (58 kB)
Downloading jinja2-3.1.6-py3-none-any.whl (134 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 134.9/134.9 kB 9.6 MB/s eta 0:00:00
Using cached pydantic-2.10.6-py3-none-any.whl (431 kB)
Using cached pydantic_core-2.27.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.0 MB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached pytz-2025.1-py2.py3-none-any.whl (507 kB)
Downloading starlette-0.46.1-py3-none-any.whl (71 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 72.0/72.0 kB 10.0 MB/s eta 0:00:00
Using cached typing_extensions-4.12.2-py3-none-any.whl (37 kB)
Using cached tzdata-2025.1-py2.py3-none-any.whl (346 kB)
Using cached et_xmlfile-2.0.0-py3-none-any.whl (18 kB)
Using cached requests-2.32.3-py3-none-any.whl (64 kB)
Using cached xyzservices-2025.1.0-py3-none-any.whl (88 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Downloading anyio-4.9.0-py3-none-any.whl (100 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100.9/100.9 kB 9.2 MB/s eta 0:00:00
Using cached certifi-2025.1.31-py3-none-any.whl (166 kB)
Using cached charset_normalizer-3.4.1-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (145 kB)
Using cached idna-3.10-py3-none-any.whl (70 kB)
Using cached MarkupSafe-3.0.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (23 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached urllib3-2.3.0-py3-none-any.whl (128 kB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Installing collected packages: pytz, xyzservices, urllib3, tzdata, typing-extensions, tabulate, sniffio, six, numpy, MarkupSafe, idna, haversine, h11, et-xmlfile, colorlog, click, charset-normalizer, certifi, annotated-types, uvicorn, requests, python-dateutil, pydantic-core, openpyxl, jinja2, anyio, starlette, pydantic, pandas, branca, folium, fastapi
Successfully installed MarkupSafe-3.0.2 annotated-types-0.7.0 anyio-4.9.0 branca-0.8.1 certifi-2025.1.31 charset-normalizer-3.4.1 click-8.1.8 colorlog-6.9.0 et-xmlfile-2.0.0 fastapi-0.115.11 folium-0.19.5 h11-0.14.0 haversine-2.9.0 idna-3.10 jinja2-3.1.6 numpy-2.2.4 openpyxl-3.1.5 pandas-2.2.3 pydantic-2.10.6 pydantic-core-2.27.2 python-dateutil-2.9.0.post0 pytz-2025.1 requests-2.32.3 six-1.17.0 sniffio-1.3.1 starlette-0.46.1 tabulate-0.9.0 typing-extensions-4.12.2 tzdata-2025.1 urllib3-2.3.0 uvicorn-0.34.0 xyzservices-2025.1.0
(uopc_virtual_env) $ 

```

Once installed, your environment is ready to use!

## 4) Run python uop.py 
```sh
python uop.py
```

Typical output:
```sh
(uopc_virtual_env) $ python uop.py
INFO
INFO     +————————————————————————————————————————————+
INFO     | UOCv1.0 running at: http://127.0.0.1:8181/ |
INFO     +————————————————————————————————————————————+
INFO
WARNING  !! Using random values !!
WARNING
INFO:     Will watch for changes in these directories: ['/mnt/c/Users/rodrirau/Desktop/yaseen-phase_II/test']
INFO:     Uvicorn running on http://127.0.0.1:8181 (Press CTRL+C to quit)
INFO:     Started reloader process [3075] using StatReload
INFO:     Started server process [3092]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
