# ravsock
Raven Distribuition Framework's Socket Server

#### Create docker image

    docker build -t ravsock .
    
#### Start a container

    docker run --name ravsock_container -p 9999:9999 ravsock

### Lint and Format 📜

![-----------------------------------------------------](https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png)

- We use [Flake8](https://flake8.pycqa.org/en/latest/manpage.html) and [Black](https://pypi.org/project/black/) for linting & formatting source code of this project.

<br>

- **Run QA checks on local environment⚡** :

  - Run Shell script on Windows 💾 :

  ```
  ...\ravsock> .\qa_checks
  ``` 

  - Run Shell script on Linux 👨‍💻 :

  ```
  .../ravsock $ ./qa_checks
  ```

  ![-----------------------------------------------------](https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png)

  - Alternate option ✔ :
    - Run this on terminal ⚡:
      - Windows 💾
        ```
        ...\ravsock> black .
        ``` 
        ```
        ...\ravsock> flake8 .
        ``` 
      - Linux 👨‍💻
        ```
        .../ravsock$ black .
        ``` 
        ```
        .../ravsock$ flake8 .
        ``` 

![-----------------------------------------------------](https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png) 