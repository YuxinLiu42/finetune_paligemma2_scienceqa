### Overall goal of the project
The goal of the project is to use natural language processing to solve a classification task of predicting whether a given tweet is about a real disaster or not.

### What framework are you going to use (Kornia, Transformer, Pytorch-Geometrics)
Since we chose a natural language processing problem, we plan to use the Transformers framework.

### How to you intend to include the framework into your project
We plan on utilizing one of the strengths of the Transformers framework which is that it provides thousands of pretrained models to perform different tasks. As a starting point we intend to use some of the pretrained models on our data and then see how we can further improve from there.

### What data are you going to run on (initially, may change)
We are using the Kaggle dataset Natural Language Processing with Disaster Tweets. Each sample in the train and test set has the following information: a unique identifier, the text of a tweet, a keyword from that tweet (although this may be blank) and the location the tweet was sent from (may also be blank) and the training set also has a target value whether a tweet is about a real disaster (1) or not (0). The dataset was chosen because it is quite simple and straightforward which makes it a great dataset for getting started with Natural Language Processing. It also seems feasible to implement in such a short timeframe.

### What deep learning models do you expect to use
We intend to use pre-trained models due to limited time, and also train the model(s) additionally on our dataset. Since we are working on tweets then one of the models we plan to use is the BERTweet model which is the first public large-scale pre-trained language model for English Tweets.

We might as well look into ALBERT and DistilBERT models, which optimize the BERT model and make the training process faster. That would be beneficial for us due to time constraints.


````markdown
# project_name

a short description

## Project structure

The directory structure of the project looks like this:
```txt
├── .github/                  # Github actions and dependabot
│   ├── dependabot.yaml
│   └── workflows/
│       └── tests.yaml
├── configs/                  # Configuration files
├── data/                     # Data directory
│   ├── processed
│   └── raw
├── dockerfiles/              # Dockerfiles
│   ├── api.Dockerfile
│   └── train.Dockerfile
├── docs/                     # Documentation
│   ├── mkdocs.yml
│   └── source/
│       └── index.md
├── models/                   # Trained models
├── notebooks/                # Jupyter notebooks
├── reports/                  # Reports
│   └── figures/
├── src/                      # Source code
│   ├── project_name/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── data.py
│   │   ├── evaluate.py
│   │   ├── models.py
│   │   ├── train.py
│   │   └── visualize.py
└── tests/                    # Tests
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_data.py
│   └── test_model.py
├── .gitignore
├── .pre-commit-config.yaml
├── LICENSE
├── pyproject.toml            # Python project file
├── README.md                 # Project README
└── tasks.py                  # Project tasks
```


Created using [mlops_template](https://github.com/SkafteNicki/mlops_template),
a [cookiecutter template](https://github.com/cookiecutter/cookiecutter) for getting
started with Machine Learning Operations (MLOps).

````
