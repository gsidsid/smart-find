#!/usr/bin/env python

from PyPDF2 import PdfFileWriter, PdfFileReader
from rake_nltk import Rake
from gensim.models import Word2Vec
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.test.utils import get_tmpfile

import re
import os
import sys
import json
import copy
import flask
import textract
import multiprocessing
import convertapi
import gensim.downloader as api

from flask import request
from flask_dropzone import Dropzone
from collections import OrderedDict

application = flask.Flask(__name__)

FILE_PATH = str(os.getcwd()) + '\econ2.pdf'
convertapi.api_secret = 'taJ7vPGswsVpSNOp'
rawtext = ""

class MultiPartBook:
    def __init__(self, path, title_page_object_dict):
        self.chapters = title_page_object_dict.keys()
        self.pages = title_page_object_dict

def structure(path):
    library = []
    pdf = None
    with open(path, 'rb') as f:
        pdf = PdfFileReader(f)
        print(pdf.getDocumentInfo())
        ols = pdf.getOutlines()
        for el in ols:
            library.append((el['/Title'],pdf.getDestinationPageNumber(el)))
    return library

def chunkText(path, library):
    library_ranged = []
    substructure_dict = dict()
    last_title = library[0][0]
    last_no = 0
    with open(path, 'rb') as f:
        pdf = PdfFileReader(f)
        for title, page_no in library:
            page_objs = []
            if (page_no-last_no) > 5:
                library_ranged.append((last_title,last_no,page_no))
                last_no = page_no
                last_title = title
    return library_ranged

def extractPdfText(filePath=''):
    fileObject = open(filePath, 'rb')
    pdfFileReader = PdfFileReader(fileObject)
    totalPageNumber = pdfFileReader.numPages
    print('This pdf file contains ' + str(totalPageNumber) + ' pages.')
    currentPageNumber = 0
    text = ''
    while(currentPageNumber < totalPageNumber ):
        pdfPage = pdfFileReader.getPage(currentPageNumber)
        text = text + pdfPage.extractText()
        currentPageNumber += 1
    return text

def rankInit(splitFile):
    data = []
    wdata = []
    for doc in splitFile:
        words = open(splitFile[doc][:-3]+"txt").read().split()
        tags = [doc]
        wdata.append(words)
        data.append(TaggedDocument(words=words, tags=tags))
    model = None
    fname = get_tmpfile("econ_model")
    if not os.path.isfile(os.getcwd() + "\\econ_model"):
        model = Doc2Vec(data, vector_size=10, window=5, min_count=1, workers=4)
        model.save(fname)
    else:
        model = Doc2Vec.load(fname)
    mod2 = Word2Vec(wdata,size=600, window=5, min_count=1, workers=4)
    return model,mod2


def chapterRank(search_space, search_t, cso):
    if search_t == None or len(search_t) == 0:
        return search_space.keys()
    else:
        narrow_space = dict()

        for chapter in search_space:
            if len(search_space[chapter]) == 0:
                search_space.pop(chapter)
            else:
                for i in range(len(search_space[chapter])):
                    if i < len(search_space[chapter]):
                        rank, keyword = search_space[chapter][i]
                        if search_t[0].lower() in keyword:
                            if chapter in narrow_space:
                                narrow_space[chapter].append((rank, keyword))
                            else:
                                narrow_space[chapter] = [(rank,keyword)]
        tail = search_t[1:]

        if len(tail) == 0:
            dc = copy.deepcopy(narrow_space)
            return dc.keys()
        else:
            return chapterRank(narrow_space, tail, cso)
            


library = structure(FILE_PATH)
substructures = chunkText(FILE_PATH, library)

inputpdf = PdfFileReader(open("econ.pdf", "rb"))
splitFile = dict()
splitFileInv = dict()

for chapter, start, end in substructures:
    splitFile[chapter] = str(os.getcwd()) + '\\split\\' + re.sub('[^A-Za-z0-9]+', '', chapter) +".pdf"
    splitFileInv[os.getcwd() + '\\split\\' + re.sub('[^A-Za-z0-9]+', '', chapter)] = chapter
    if not os.path.isfile(splitFile[chapter]):
        output = PdfFileWriter()
        for i in range(start, end):     
            output.addPage(inputpdf.getPage(i))
        with open(splitFile[chapter], "wb") as outputStream:
            output.write(outputStream)

for key in splitFile:
    s = splitFile[key][:-3]+"txt" 
    if not os.path.isfile(s):
        try:
            convertapi.convert('txt', {
                'File': splitFile[key]
            }, from_format = 'pdf').save_files(os.getcwd() + "\\split")
        except: 
            continue;

r = Rake()
cs = dict()
for key in splitFile:
    s = splitFile[key][:-3]+"txt" 
    with open(s,'r') as f:
        content = f.read()
        rawtext += content.decode('utf-8')
        r.extract_keywords_from_text(content.decode('utf-8'))
        c = (r.get_ranked_phrases_with_scores()) 
        d = []
        maxr = max(c, key = lambda x: x[0])[0]
        for rank, kw in c:
            d.append((rank/maxr,kw.encode('utf-8')))
        cs[key] = d

#model,model2 = rankInit(splitFile)


@application.route('/<val>')
def innerRanking(val):
    res = chapterRank(cs, val.encode('utf-8').split(' '), cs)
    return flask.Response(json.dumps(res), status=200, mimetype='application/json')


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 33507))
    application.run(host='0.0.0.0',port=port)
