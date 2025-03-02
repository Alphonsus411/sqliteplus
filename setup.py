from setuptools import setup, find_packages

setup(
    name="sqliteplus",
    version="1.0.0",
    author="Tu Nombre",
    author_email="tuemail@example.com",
    description="SQLite mejorado con cifrado SQLCipher y caché en Redis",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Alphonsus411/sqliteplus",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "fastapi",
        "uvicorn",
        "redis",
        "bcrypt",
        "PyJWT",
        "pytest",
        "setuptools"
    ],
    entry_points={
        "console_scripts": [
            "sqliteplus=sqliteplus.cli:cli"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
