### Localz

Package localisation for Rez.

<br>

### Usage

**Prerequisities**

- `rez-2.29+`
- `python-2.7,<4`

Used as a Rez package.

```bash
$ git clone https://github.com/mottosso/rez-localz.git
$ cd rez-localz
$ rez build --install
```

Once installed, you can start localising packages like this.

```bash
$ rez env localz -- localise Qt.py
```

This will localise the [Qt.py]() package onto your `config.local_packages_path`.

#### Multiple requests

Localise multiple packages at once, that all resolve to one another making sure they work together.

```bash
$ rez env localz -- localise maya-2018 arnold flex
```

#### Full context

Localise an entire context with the `--full` flag.

```bash
$ rez env localz -- localise maya alita gitlab --full
```
