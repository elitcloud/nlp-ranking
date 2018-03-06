import os
import re
import glob
import codecs
from types import SimpleNamespace

import bibtexparser
import matplotlib.pyplot as plt
import requests



def load_map(map_file):
    """
    :param map_file: bib_map.tsv
    :return: a dictionary where the key is the conference/journal ID and the value is a namespace of (weight, series).
    """
    fin = open(map_file)
    d = {}

    for i, line in enumerate(fin):
        l = line.strip().split('\t')
        if len(l) == 3:
            key = l[0]
            d[key] = SimpleNamespace(weight=float(l[1]), series=l[2])

    return d

MAP_FILE = '../dat/bib_map.tsv'  # change this to your local path
bib_map = load_map(MAP_FILE)
print(bib_map['P17-1'])



def crawl_aclbib(bib_map, bib_dir):
    """
    Crawl bib files from ACL Anthology.
    :param bib_map: the output of load_map().
    :param bib_dir: the output directory where the bib files are stored.
    """
    re_bib = re.compile('<a href="([A-Z]\d\d-\d\d\d\d\.bib)">bib</a>')
    acl = 'http://www.aclweb.org/anthology'

    for k, v in bib_map.items():
        out = os.path.join(bib_dir, k + '.bib')
        if os.path.isfile(out): continue  # skip if already downloaded
        fout = open(out, 'w')
        print(out)

        root_url = os.path.join(acl, k[0], k[:3])  # http://www.aclweb.org/anthology/P/P17
        r = requests.get(os.path.join(root_url, k + '.bib'))  # http://www.aclweb.org/anthology/P/P17/P17-1.bib
        text = r.text.strip()

        if text.startswith('@'):  # bib collection is provided
            fout.write(r.text)
        else:  # bib files are provided individually per papers
            r = requests.get(root_url)

            for bib in re_bib.findall(r.text):
                if bib[:6] in bib_map: continue  # skip specially handled workshops (e.g., CoNLL)
                rs = requests.get(os.path.join(root_url, bib))
                fout.write(rs.text)

        fout.close()


BIB_DIR = '../bib/'
crawl_aclbib(bib_map, BIB_DIR)
print(len(glob.glob(os.path.join(BIB_DIR, '*.bib'))))



def get_entry_dict(bib_map, bib_dir):
    """
    :param bib_map: the output of load_map().
    :param bib_dir: the input directory where the bib files are stored.
    :return: a dictionary where the key is the publication ID (e.g., 'P17-1000') and the value is its bib entry.
    """
    re_pages = re.compile('(\d+)-{1,2}(\d+)')

    def parse_name(name):
        if ',' in name:
            n = name.split(',')
            if len(n) == 2: return n[1].strip() + ' ' + n[0].strip()
        return name

    def get(entry, weight, series):
        entry['author'] = [parse_name(name) for name in entry['author'].split(' and ')]
        entry['weight'] = weight
        entry['series'] = series
        return entry['ID'], entry

    def valid(entry, weight):
        if weight == 1.0:
            if 'pages' in entry:
                m = re_pages.search(entry['pages'])
                return m and int(m.group(2)) - int(m.group(1)) > 4
            return False

        return 'author' in entry

    bibs = {}
    for k, v in bib_map.items():
        fin = open(os.path.join(bib_dir, k + '.bib'))
        try:
            bib = bibtexparser.loads(fin.read())
        except IndexError as e:
            continue
        bibs.update([get(entry, v.weight, v.series) for entry in bib.entries if valid(entry, v.weight)])
    return bibs

entry_dict = get_entry_dict(bib_map, BIB_DIR)
print(entry_dict['K17-1023']['author'])
print(len(entry_dict))



def get_email_dict(txt_dir):
    """
    :param txt_dir: the input directory containing all text files.
    :return: a dictionary where the key is the publication ID and the value is the list of authors' email addresses.
    """
    def chunk(text_file, page_limit=2000):
        fin = codecs.open(text_file, encoding='utf-8')
        doc = []
        n = 0

        for line in fin:
            line = line.strip().lower()
            if line:
                doc.append(line)
                n += len(line)
                if n > page_limit: break

        return ' '.join(doc)

    re_email = re.compile('[({\[]?\s*([a-z0-9\.\-_]+(?:\s*[,;|]\s*[a-z0-9\.\-_]+)*)\s*[\]})]?\s*@\s*([a-z0-9\.\-_]+\.[a-z]{2,})')
    email_dict = {}

    for txt_file in glob.glob(os.path.join(txt_dir, '*.txt')):
        try:
            doc = chunk(txt_file)
        except UnicodeDecodeError:
            # print(txt_file)
            continue
        emails = []

        for m in re_email.findall(doc):
            ids = m[0].replace(';', ',').replace('|', ',')
            domain = m[1]

            if ',' in ids:
                emails.extend([ID.strip()+'@'+domain for ID in ids.split(',') if ID.strip()])
            else:
                emails.append(ids+'@'+domain)

        if emails:
            key = os.path.basename(txt_file)[:-4]
            email_dict[key] = emails

    return email_dict

TXT_DIR = '../txt/'
email_dict = get_email_dict(TXT_DIR)
print(len(email_dict))



def load_emails(email_file):
    fin = open(email_file)
    d = {}

    for line in fin:
        l = line.split('\t')
        d[l[0]] = SimpleNamespace(num_authors=int(l[1]), emails=l[2:])

    fin.close()
    return d

email_file = load_emails('../dat/email_map.tsv')
print(email_file['C12-1026'])



def firstname_lastname(email_file):
    re_firstname_lastname = re.compile(r'\{?(first[\-\s]?name)[\._](last[\-\s]?name)\}?@\s*([a-z0-9\.\-_]+\.[a-z]{2,})')
    d = {}
    for k, v in email_file.items():
        emails = v.emails
        num_authors = v.num_authors
        length = len(emails)
        n = num_authors - length
        for email in emails:
            s = re_firstname_lastname.search(email)
            if s:
                st = [s.group(0)]
                for i in range(n):
                    emails.extend(st)
                break
        d[k] = SimpleNamespace(num_authors=num_authors, emails=emails)
    return d

new_namespace = firstname_lastname(email_file)
print(firstname_lastname(email_file)['C12-1026'])



def new_email_dict(email_dict, new_namespace):
    for k, v in new_namespace.items():
        email_dict[k] = v.emails
    return email_dict

new_email_dict = new_email_dict(email_dict, new_namespace)
print(new_email_dict['C12-1026'])
print(len(new_email_dict))



def domain_weight(emails):
    r = re.compile(r'(?:@)(?:[a-zA-Z0-9-]+\.?[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+\.[a-z]{2,})')
    d = {}
    for email in emails:
        s = r.search(email)
        if s:
            if s.group(1) in d:
                d[s.group(1)].append(s.group(1))
            else:
                d[s.group(1)] = [s.group(1)]
    d = {k: len(v)/len(emails) for k, v in d.items()}

    return d

print(new_email_dict['C10-2121'])
print(domain_weight(new_email_dict['C10-2121']))



def print_emails(entry_dict, email_dict, email_file):
    """
    :param entry_dict: the output of get_entry_dict().
    :param email_dict: the output of get_email_dict().
    :param email_file: the output file in the TSV format, where each column contains
                       (publication ID, the total number of authors, list of email addresses) for each paper.
    """
    fout = open(email_file, 'w')

    for k, v in sorted(entry_dict.items()):
        n = len(v['author'])
        l = [k, str(n)]
        if k in email_dict:
            l.extend([email+';' for email in email_dict[k]])
            st = ''
            for key,val in domain_weight(email_dict[k]).items():
                st = st + key + ':' + str(val) + ';'
            l.append(st)
        fout.write('\t'.join(l) + '\n')

    fout.close()

EMAIL_FILE = '../dat/email_map_ryan_joye.tsv'
print_emails(entry_dict, new_email_dict, EMAIL_FILE)



def load_institutes(institute_file):
    fin = open(institute_file)
    d = {}

    for line in fin:
        l = line.split('\t')
        d[l[1]] = SimpleNamespace(name=l[0], city=l[2], state=l[3])

    fin.close()
    return d

INSTITUTE_FILE = '../dat/us_institutes_ryan_joye.txt'
institute_dict = load_institutes(INSTITUTE_FILE)
print(len(institute_dict))



def rank_dict(email_dict, institute_dict, US_universities=False):
    D = {}
    for key, value in email_dict.items():
        if US_universities:
            institute_dict = load_institutes(INSTITUTE_FILE)
            d = domain_weight(value)
            for k, v in d.items():
                if k in institute_dict:
                    if k in D:
                        D[k] = D[k] + v
                    else:
                        D[k] = v
        else:
            d = domain_weight(value)
            for k, v in d.items():
                if k in D:
                    D[k] = D[k] + v
                else:
                    D[k] = v
    for k in institute_dict:
        if k in D:
            D[institute_dict[k].name] = D.pop(k)
    return D

ranked_dict = rank_dict(new_email_dict, institute_dict, US_universities=True)
print(sorted(ranked_dict.items(), key=lambda x: x[1], reverse=True))
