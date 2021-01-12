from neomodel import db,config, StructuredNode, StringProperty
from db import *
import sys
from datetime import datetime
from operator import attrgetter


def migrate():
    matching_dict = {"Act": {'DATE_OF_DOCUMENT': 'date_of_document', 'DATE_OF_EFFECT': 'date_of_effect',
                             'DATE_OF_VALIDITY': 'date_of_validity', 'DEADLINE': 'deadline',
                             'CONCERNS': 'concerns', 'CLASSIFICATION': 'classification',
                             'DIRECTORY': 'directory', 'AUTHOR': 'author', 'FORM': 'form',
                             'RELEVANT': 'relevant', 'TREATY': 'treaty', 'CITES': 'cites',
                             'BASED': {'Act': 'based_act', 'Article': 'based_article'},
                             'CONSISTS': 'consists', 'REGULATES': 'regulated_entities',
                             'MENTIONS': 'mentioned_entities'},
                     "Article": {'MENTIONS': 'mentioned_entities', 'DEFINES': 'defined_entities',
                                 'REGULATES': 'regulated_entities'}}



    db.set_connection('bolt://neo4j:1@localhost:7687')
    #db.set_connection('bolt://neo4j:recapitulation-jails-dates@100.25.33.237:38562')
    results, meta = db.cypher_query("MATCH p=()-->() RETURN p")
    db.set_connection('bolt://neo4j:changes-hour-mass@100.26.226.98:34409')

    for result in results:

        start_node_label = list(result[0].start_node.labels)[0]
        start_node_class = getattr(sys.modules[__name__], start_node_label)
        start_node = start_node_class.get_or_create(result[0].start_node)[0]
        end_node_label = list(result[0].end_node.labels)[0]
        end_node_class = getattr(sys.modules[__name__], end_node_label)


        if end_node_label == "Date":
            date = datetime.strptime(result[0].end_node._properties['date'], '%Y-%m-%d').date()

            try:
                end_node = Date.nodes.get(date=date)
            except DoesNotExist:
                end_node = Date(date=date)
                end_node.save()
        else:
            end_node = end_node_class.get_or_create(result[0].end_node)[0]


        rel_type = result[0].relationships[0].type
        rel_properties = result[0].relationships[0]._properties
        rel_attr = matching_dict[start_node_label][rel_type]
        if not type(rel_attr) is str:
            rel_attr = rel_attr[end_node_label]
        try:
            rel = attrgetter(rel_attr)(start_node).connect(end_node)

        except:
            print("failed to get an attr for {0} with attr {1}".format(start_node, rel_attr))
        for key, value in rel_properties.items():

            rel.__dict__[key] = value
            rel.save()



migrate()
