from neomodel import (config, StructuredNode, StructuredRel, StringProperty, IntegerProperty,
    UniqueIdProperty, DateTimeProperty, DateProperty, ArrayProperty, RelationshipTo, DoesNotExist,
                      BooleanProperty)
import pandas as pd
import itertools


class DateRel(StructuredRel):
    comment = StringProperty()


class Date(StructuredNode):
    uid = UniqueIdProperty()
    date = DateProperty(unique_index=True)

class EurovocDescriptor(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)

class SubjectMatter(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)

class DirectoryCode(StructuredNode):
    uid = UniqueIdProperty()
    code = StringProperty(unique_index=True)
    name = StringProperty()

class Author(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)

class Form(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)

class RelevanceArea(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)

class Treaty(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)


class LegalTerm(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    #full_name = StringProperty(unique_index=True)
    nested = BooleanProperty()
    mentioned_as = ArrayProperty(StringProperty())

    @classmethod
    def highest_match(cls, text, df):
        from fuzzywuzzy import process

        names = df['name'].tolist()
        if names:
            highest = process.extractOne(text, names)
            if highest[1] >= 85:
                results = df.loc[df['name'] == highest[0]].legal_term.values
                return results
        return []

    @classmethod
    def max_ratio(cls, text, df):
        from fuzzywuzzy import fuzz

        df['ratio'] = df[['name']].apply(lambda x: fuzz.token_set_ratio(text.lower(),
                                                                            str(x.get('name')).lower()), axis=1)
        '''ratio = list(map(lambda x: tuple([fuzz.token_set_ratio(text.lower(), x.lower()), x]), mentioned))
        ratio_df = pd.DataFrame.from_records(ratio, columns=['ratio', 'mentioned'])'''
        max = df['ratio'].max()
        if max > 85:
            max_terms = df.loc[df['ratio'] == max].legal_term.values
            if len(max_terms) == 1:
                results = max_terms
                return results
            else:
                print("couldn't identify legal_term {} from existing terms {}. failed to match".format(text,
                                                                                                       max_terms))
        return []

    @classmethod
    def match(cls, nested, text):
        from neomodel import db

        # for old neo4j
        '''results, meta = db.cypher_query("MATCH (l:LegalTerm) WHERE {text} in l.mentioned_as RETURN l",
                                        {'text': text})'''
        # for new neo4j
        results, meta = db.cypher_query("MATCH (l:LegalTerm) WHERE $text in l.mentioned_as RETURN l",
                                        {'text': text})
        results = list(map(lambda x: LegalTerm.inflate(x[0]), results))

        if not results:
            # for old neo4j
            '''all_results, meta = db.cypher_query("MATCH (l:LegalTerm) WHERE l.nested = {nested} RETURN l, l.mentioned_as ",
                                        {'nested': nested})'''

            # for new neo4j
            all_results, meta = db.cypher_query(
                "MATCH (l:LegalTerm) WHERE l.nested = $nested RETURN l ",
                {'nested': nested})

            df = pd.DataFrame(
                list(map(lambda x: LegalTerm.inflate(x[0]), all_results)),
                columns=['legal_term'])
            df['name'] = df['legal_term'].apply(lambda x: x.name)

            results = cls.highest_match(text, df)

        if not results and not nested:

            results = cls.max_ratio(text, df)


        if len(results) > 1:
            print("couldn't identify legal_term {} from existing terms {}. failed to match".format(text,
                                                                                                   results))
            return None

        if len(results) == 1:
            term = results[0]
            if not text in term.mentioned_as:
                term.mentioned_as.append(text)


        elif not results:
            term = LegalTerm(name=text, nested=nested)
            term.mentioned_as = [text]
        term.save()
        return term






class Article(StructuredNode):
    uid = UniqueIdProperty()
    code = StringProperty()
    name = StringProperty()
    title = StringProperty()

    mentioned_entities = RelationshipTo(LegalTerm, 'MENTIONS')
    defined_entities = RelationshipTo(LegalTerm, 'DEFINES')
    regulated_entities = RelationshipTo(LegalTerm, 'REGULATES')


    @classmethod
    def get_article(cls, act, search_params, create_params=None):
        if not create_params:
            create_params = search_params
        articles = act.article_from_consist(search_params)
        if not articles:
            article = Article(**create_params)
            article.save()
            act.consists.connect(article)
            return article
        elif len(articles) == 1:
            article = articles[0]
            return article
        else:
            print("article search_params {0} for act {1} is ambiguous. "
                  "failed to relate based article".format(search_params, act))




class Act(StructuredNode):
    uid = UniqueIdProperty()
    short_title = StringProperty()
    title = StringProperty()
    full_title = StringProperty()
    celex_id = StringProperty(unique_index=True)

    date_of_document = RelationshipTo(Date, 'DATE_OF_DOCUMENT', model=DateRel)
    date_of_effect = RelationshipTo(Date, 'DATE_OF_EFFECT', model=DateRel)
    date_of_validity = RelationshipTo(Date, 'DATE_OF_VALIDITY', model=DateRel)
    deadline = RelationshipTo(Date, 'DEADLINE', model=DateRel)

    concerns = RelationshipTo(SubjectMatter, 'CONCERNS')
    classification = RelationshipTo(EurovocDescriptor, 'CLASSIFICATION')
    directory = RelationshipTo(DirectoryCode, 'DIRECTORY')

    author = RelationshipTo(Author, 'AUTHOR')
    form = RelationshipTo(Form, 'FORM')
    relevant = RelationshipTo(RelevanceArea, 'RELEVANT')

    treaty = RelationshipTo(Treaty, 'TREATY')

    cites = RelationshipTo('Act', 'CITES')
    based_act = RelationshipTo('Act', 'BASED')
    based_article = RelationshipTo(Article, 'BASED')

    consists = RelationshipTo(Article, 'CONSISTS')

    regulated_entities = RelationshipTo(LegalTerm, 'REGULATES')
    mentioned_entities = RelationshipTo(LegalTerm, 'MENTIONS')

    @classmethod
    def match(cls, celex_id):
        try:
            act = cls.nodes.get(celex_id=celex_id)

        except DoesNotExist:
            act = cls(celex_id=celex_id)
            act.short_title = celex_id
            act.save()


        if not act.short_title:
            act.short_title = celex_id
            act.save()
        return act




    def article_from_consist(self, params):
        text = "MATCH (a) WHERE id(a)=$self MATCH (a)-[r:CONSISTS]->(ar:Article {"
        param_dict = {}

        i = 0
        for key, value in params.items():
            text = ''.join([text, key, ": $",'p', str(i), ""])
            param_dict['p' + str(i)] = value
            i += 1
            if i < len(params):
                text = ''.join([text, ", "])
        text = ''.join([text, "}) RETURN ar"])

        #'MATCH (a) WHERE id(a)={self} MATCH (a)-[r:CONSISTS]->(ar:Article {code: $p0}) RETURN ar'

        results, columns = self.cypher(text, param_dict)
        return [Article.inflate(row[0]) for row in results]



from neomodel import install_labels, remove_all_labels, install_all_labels
#config.DATABASE_URL = 'bolt://neo4j:recapitulation-jails-dates@100.25.33.237:38562'
#config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'
#config.DATABASE_URL = 'bolt://neo4j:changes-hour-mass@100.26.226.98:34409'

#remove_all_labels()
#install_all_labels()

