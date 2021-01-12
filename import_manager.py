from bs4 import BeautifulSoup
import urllib.request
from neomodel import config, DoesNotExist
from db import *
from predict import predict_text_entity_extraction
import itertools
from datetime import datetime
from operator import attrgetter

class Date_ax():
    def __init__(self, type, date, comment=None):
        self.type = type
        self.date = date
        self.comment = comment

class Legal_ax():
    def __init__(self, celexid = None, article = None, comment=None):
        self.celexid = celexid
        self.article = article
        #self.comment = comment

class Mentioning():
    def __init__(self):
        self.mention = "mention"
        self.regulate = "regulate"



class ImportManager:
    def __init__(self, file_path):
        self.soup = self.read_from_html(file_path)
        self.current_act = None
        self.analytics_dict = {}

    def read_from_html(self, file_path):
        try:
            html = urllib.request.urlopen(file_path).read()
            return BeautifulSoup(html, "lxml")
        except Exception as e:
            print(e.args)
            raise ValueError("failed to open html-file")

    def read_doc_titles(self):
        try:
            self.current_act.title = self.soup.find_all('p', attrs={'class': "doc-ti"})[0].text

        except Exception as e:
            try:
                self.current_act.title = self.soup.find_all('p', attrs={'class': "oj-doc-ti"})[0].text
            except Exception as e1:
                print(e.args)
                raise ValueError("failed to identify title, make sure html-file has the right format")

        if self.current_act.title:
            short_title = "".join(itertools.dropwhile(lambda x: not x.isdigit(),
                                                      self.current_act.title)).split(" ")

            self.current_act.short_title = "".join(itertools.takewhile(lambda x: x != "OF",
                                                                       short_title))
        try:
            self.current_act.full_title = " ".join([self.soup.find_all('p', attrs={'class': "doc-ti"})[0].text,
                                                    self.soup.find_all('p', attrs={'class': "doc-ti"})[1].text,
                                                    self.soup.find_all('p', attrs={'class': "doc-ti"})[2].text])
        except Exception as e:
            try:
                self.current_act.full_title = " ".join([self.soup.find_all('p', attrs={'class': "oj-doc-ti"})[0].text,
                                                        self.soup.find_all('p', attrs={'class': "oj-doc-ti"})[1].text,
                                                        self.soup.find_all('p', attrs={'class': "oj-doc-ti"})[2].text])
            except Exception as e1:
                print(e.args)
                raise ValueError("failed to identify full_title, make sure html-file has the right format")

    def import_current_act(self):
        try:
            celex_id = self.soup.find_all('meta', attrs={'name': "WT.z_docID"})[0].attrs.get('content')
        except Exception as e:
            print(e.args)
            raise ValueError("failed to identify CELEXID, make sure html-file has the right format")

        #original path, to local database
        #config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'
        # path to the database deployed on the cloud to test our app without creating a local db
        config.DATABASE_URL = 'bolt://neo4j:changes-hour-mass@100.26.226.98:34409'


        try:
            self.current_act = Act.nodes.get(celex_id=celex_id)
        except DoesNotExist:
            self.current_act = Act(celex_id=celex_id)

        try:
            self.read_doc_titles()
        except Exception as e:
            print(e.args)
            raise ValueError("failed to identify doc titles, make sure html-file has the right format")

        self.current_act.save()


    def read_dates(self):
        dates = []
        if self.analytics_dict["Date of document: "]:
            date = False
            for el in self.analytics_dict["Date of document: "][0].split(";"):

                try:
                    current_date = datetime.strptime(el, '%d/%m/%Y').date()
                    date = Date_ax(type="date_of_document", date=current_date)

                except Exception as ex:
                    if date:
                        date.comment = "".join(list(filter(None, [date.comment, el])))
            if date:
                dates.append(date)

        dates_dict = {"Date of effect: ": "date_of_effect", "Date of end of validity: ": "date_of_validity",
                      "Deadline: ": 'deadline'}
        for key, value in dates_dict.items():
            date = False
            for e in self.analytics_dict[key]:
                for el in e.split(";"):

                    try:
                        current_date = datetime.strptime(el, '%d/%m/%Y').date()
                        if date:
                            dates.append(date)
                        date = Date_ax(type=value, date=current_date)

                    except Exception as ex:
                        if date:
                            date.comment = "".join(list(filter(None, [date.comment, el])))

            if date:
                dates.append(date)

        return dates


    def create_date_relationships(self):

        type_sorted_dates = sorted(self.read_dates(), key=lambda x: x.type)
        for type, type_group in itertools.groupby(type_sorted_dates, lambda x: x.type):
            sorted_dates = sorted(list(type_group), key=lambda x: x.date)

            for date, date_group in itertools.groupby(sorted_dates, lambda x: x.date):
                comment = ""
                try:
                    current_date = Date.nodes.get(date=date)

                except DoesNotExist:
                    current_date = Date(date=date)
                    current_date.save()
                for e in date_group:
                    comment = "".join(list(filter(None, [comment, e.comment])))

                rel_attr = attrgetter(type)(self.current_act)
                rel = rel_attr.connect(current_date)

                if comment:
                    rel.comment = comment
                    rel.save()

    def predict_entities(self, text):
        import pandas as pd
        predictions = predict_text_entity_extraction(content=text)
        self.prediction_df = pd.DataFrame([])
        for prediction in predictions:
            self.prediction_df = self.prediction_df.append(pd.DataFrame(dict(prediction.items())))


    def filter_labels(self, text, filter=None, accuracy=None):
        entities = []
        if filter:
            df = self.prediction_df.loc[self.prediction_df['displayNames'].isin(filter)]
        else:
            df = self.prediction_df
        if accuracy:
            df = df.loc[df['confidences'] > accuracy]
        starts = list(map(lambda x: int(x), df['textSegmentStartOffsets']))
        ends = list(map(lambda x: int(x), df['textSegmentEndOffsets']))
        labels = list(map(lambda x: x, df['displayNames']))
        current_entities = list(map(lambda x: tuple([x[2], text[x[0]:x[1]]]), zip(starts, ends, labels)))
        entities.extend(current_entities)
        return entities

    def eurovoc_descriptor(self, x):
        try:
            eurovoc_descriptor = EurovocDescriptor.nodes.get(name=x)

        except DoesNotExist:
            eurovoc_descriptor = EurovocDescriptor(name=x)
            eurovoc_descriptor.save()
        self.current_act.classification.connect(eurovoc_descriptor)

    def subject_matter(self, x):
        try:
            subject_matter = SubjectMatter.nodes.get(name=x)

        except DoesNotExist:
            subject_matter = SubjectMatter(name=x)
            subject_matter.save()
        self.current_act.concerns.connect(subject_matter)

    def author(self, x):
        try:
            author = Author.nodes.get(name=x)

        except DoesNotExist:
            author = Author(name=x)
            author.save()
        rel = self.current_act.author.connect(author)

    def form(self, x):
        try:
            form = Form.nodes.get(name=x)

        except DoesNotExist:
            form = Form(name=x)
            form.save()
        self.current_act.form.connect(form)

    def relevance_area(self, text):
        #COMMENTED FOR DEBUGGING
        #DO NOT FORGET TO UNCOMMENT
        self.predict_entities(text)
        relevance = self.filter_labels(text, ['relevance_area'], 0.85)
        relevance = [("", "EEA")]
        for relevance_area in relevance:
            try:
                relevance_area = RelevanceArea.nodes.get(name=relevance_area[1])

            except DoesNotExist:
                relevance_area = RelevanceArea(name=relevance_area[1])
                relevance_area.save()
            self.current_act.relevant.connect(relevance_area)



    def read_analytics(self):

        if self.analytics_dict["EUROVOC descriptor: "]:
            eurovoc_descriptor = list(map(lambda x: self.eurovoc_descriptor(x),
                                               self.analytics_dict["EUROVOC descriptor: "]))

        if self.analytics_dict["Subject matter: "]:
            subject_matter = list(map(lambda x: self.subject_matter(x),
                                           self.analytics_dict["Subject matter: "]))

        if self.analytics_dict["Directory code: "]:

            code = self.analytics_dict["Directory code: "][0]
            try:
                directory_code = DirectoryCode.nodes.get(code=code)

            except DoesNotExist:
                directory_code = DirectoryCode(code=code)

            if len(self.analytics_dict["Directory code: "]) > 1:
                directory_code.name = self.analytics_dict["Directory code: "][1]
                directory_code.save()
            self.current_act.directory.connect(directory_code)

        for el in self.analytics_dict["Author: "]:
            author = list(map(lambda x: self.author(x),
                                           el.split(", ")))

        if self.analytics_dict["Form: "]:
            form = list(map(lambda x: self.form(x),
                                           self.analytics_dict["Form: "]))

        for el in self.analytics_dict["Additional information: "]:
            self.relevance_area(el)



    def relate_act(self, celex_id, attr_name):
        rel_attr = attrgetter(attr_name)(self.current_act)

        try:
            act = Act.nodes.get(celex_id=celex_id)

        except DoesNotExist:
            act = Act(celex_id=celex_id)
            act.short_title = celex_id
            act.save()

        if not act.short_title:
            act.short_title = celex_id
            act.save()
        rel_attr.connect(act)
        return act

    def read_legal_basis(self):
        legal_basis = []
        for basis in self.analytics_dict["Legal basis: "]:
            data = [list(filter(None, e.split(" "))) for e in basis.split("-")]
            for i, e in enumerate(data):
                if e:
                    legal = Legal_ax(celexid=e[0])
                    legal_basis.append(legal)
                if i+1 < len(data):
                    value = data[i+1].pop(0)
                    legal.article = value

        return legal_basis

    def create_basis_relationships(self):

        legal_basis = self.read_legal_basis()
        sorted_ = sorted(legal_basis, key=lambda x: x.celexid)

        for key, group in itertools.groupby(sorted_, lambda x: x.celexid):

            act = Act.match(key)
            article = None
            for e in group:
                if e.article:
                    if e.article[0] == "A":
                        name = "".join(list(itertools.takewhile(lambda x: x!="P", e.article)))
                        code = name[1:]
                        name = "".join(["Article ", code])
                        article = Article.get_article(act, {"code": code}, {"code": code, "name": name})
                        if article:
                            self.current_act.based_article.connect(article)

            if not article:
                self.current_act.based_act.connect(act)


    def read_links(self):
        for el in self.analytics_dict["Treaty: "]:
            try:
                treaty = Treaty.nodes.get(name=el)

            except DoesNotExist:
                treaty = Treaty(name=el)
                treaty.save()
            self.current_act.treaty.connect(treaty)

        if self.analytics_dict["Instruments cited: "]:
            cited = list(map(lambda x: self.relate_act(x, 'cites'),
                                           self.analytics_dict["Instruments cited: "]))

        self.create_basis_relationships()


    def read_metadata(self):
        analytics = self.soup.find_all('dl', attrs={'class': "NMetadata"})
        self.analytics_dict = {"Date of document: ": [], "Date of effect: ": [], "Date of end of validity: ": [],
                               "Deadline: ": [],
                               "EUROVOC descriptor: ": [], "Subject matter: ": [], "Directory code: ": [],
                               "Author: ": [], "Form: ": [], "Additional information: ": [],
                               "Instruments cited: ": [], "Treaty: ":[], "Legal basis: ": [], "Proposal: ": [],
                               "Link": []}

        for row in analytics:
            try:
                contents = list(filter(None, row.text.split("\n")))
                current_key = False
                for e in contents:
                    if e in self.analytics_dict.keys():
                        current_key = e
                    elif current_key:
                        self.analytics_dict[current_key].append(e)
            except Exception as e:
                print(e.args)
                print("no analytics were found in a row: ", row)


        self.create_date_relationships()
        self.read_analytics()
        self.read_links()


    def relate_mentioned_entities(self, text, attr_name, starting_node):

        rel_attr = attrgetter(attr_name)(starting_node)
        self.predict_entities(text)
        legal_terms = self.filter_labels(text, ['legal_term', 'legal_term_nested'], accuracy=0.85)
        for legal_term in legal_terms:
            nested = False if legal_term[0] == 'legal_term' else True
            term = LegalTerm.match(nested, legal_term[1])
            if term:
                rel_attr.connect(term)


    def read_panel_body(self):
        try:
            title = self.soup.find_all('p', attrs={'class': "doc-ti"})[2].text
        except:
            title = self.soup.find_all('p', attrs={'class': "oj-doc-ti"})[2].text
        self.relate_mentioned_entities(title, 'regulated_entities', self.current_act)

        mentioning = Mentioning()
        text = self.soup.find_all('div', attrs={'class': "panel-body", 'id': "text"})

        ax_dict = {"doc-ti": False, "normal": False, "ti-art": False, "sti-art": False}
        try:
            text = text[0].div.div.div.div
            for element in text:
                try:
                    if "doc-ti" in element.attrs['class'] or "oj-doc-ti" in element.attrs['class']:
                        ax_dict["doc-ti"] = True
                    elif "ti-art" in element.attrs['class'] or "oj-ti-art" in element.attrs['class']:
                        ax_dict["doc-ti"] = False
                        ax_dict["ti-art"] = True
                        name = element.text
                        code = name.replace('Article ', '')

                        article = Article.get_article(self.current_act, {"code": code}, {"code": code, "name": name})


                    elif "sti-art" in element.attrs['class'] or "oj-sti-art" in element.attrs['class']:
                        defines = True if element.text == "Definitions" else False
                        article.title = element.text
                        article.save()

                        self.relate_mentioned_entities(element.text, 'regulated_entities', article)
                    elif "normal" in element.attrs['class'] or "oj-normal" in element.attrs['class']:
                        if ax_dict["doc-ti"]:
                            self.relate_mentioned_entities(element.text, 'mentioned_entities', self.current_act)
                        elif ax_dict["ti-art"]:
                            if defines:
                                self.relate_mentioned_entities(element.text, 'defined_entities', article)
                            else:
                                self.relate_mentioned_entities(element.text, 'mentioned_entities', article)

                    elif "final" in element.attrs['class'] or "oj-final" in element.attrs['class']:
                        ax_dict["doc-ti"] = True
                        ax_dict["ti-art"] = False
                        self.relevance_area(element.text)

                        break
                    else:
                        if ax_dict["doc-ti"]:
                            self.relate_mentioned_entities(element.text, 'mentioned_entities', self.current_act)
                            #pass
                        elif ax_dict["ti-art"]:
                            if defines:
                                self.relate_mentioned_entities(element.text, 'defined_entities', article)
                                #pass
                            else:
                                self.relate_mentioned_entities(element.text, 'mentioned_entities', article)
                                #pass
                        #continue
                except:
                    try:
                        element.attrs
                        '''if ax_dict["doc-ti"]:
                            self.relate_mentioned_entities(element.text, 'mentioned_entities', self.current_act)
                        elif ax_dict["ti-art"]:'''
                        if ax_dict["ti-art"]:
                            if defines:
                                self.relate_mentioned_entities(element.text, 'defined_entities', article)
                                #pass
                            else:
                                self.relate_mentioned_entities(element.text, 'mentioned_entities', article)
                                #pass
                        else:
                            continue
                    except:
                        continue

        except Exception as e:
            print(e.args)
            print("failed to read the body, make sure html-file conforms with acceptable structure")




    def import_data(self):
        try:
            self.import_current_act()
        except Exception as e:
            raise ValueError(e.args)

        self.read_metadata()
        self.read_panel_body()

        pass




#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32012R0648 - EN - EUR-Lex.html'
file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32014R0484 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32013R0575 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32013R0153 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32013R0152 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32013R0149 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32015R2205 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32016R0592 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32016R1178 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32019R0397 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32017R0751 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32014R0285 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32013R0876 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32020R0447 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32012R0826 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32015L0849 - EN - EUR-Lex.html'
#file_path = 'file:///home/nataly/Nataly/AI/Bootcamp/Data for Google/html/EUR-Lex - 32015R2365 - EN - EUR-Lex.html'








import_manager = ImportManager(file_path)
import_manager.import_data()

