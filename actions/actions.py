# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/core/actions/#custom-actions/

import json
from typing import Any, Text, Dict, List
import random

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from treelib import Node, Tree
from rasa_sdk.events import SlotSet, UserUtteranceReverted, ActionReverted
from rasa_sdk.forms import FormAction

symptoms = []
current_symptoms = []
current_target = None

class ActionProvideRequestedAttackInformation(Action):

    def name(self) -> Text:
        return "action_provide_requested_attack_information"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # requested_attack = None
        supported_attacks = self.__get_supported_attacks()
        print("SUPPORTED ATTACKS: " + str(supported_attacks))

        referred_attacks = self.__get_referred_attacks(dispatcher, tracker, domain)

        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            # print("Be more specific. Please rephrase and include the attack(s) you are interested in. [1] [attack information]")
            return [UserUtteranceReverted()]

        #requested attacks
        print(str(referred_attacks))
        
        # if attack is not available in JSON file
        invalid_attacks = []
        for attack in referred_attacks:
            if attack not in supported_attacks:
                invalid_attacks.append(attack)

        # remove attacks which are not covered in JSON file
        if len(invalid_attacks) != 0:
            for invalid_attack in invalid_attacks:
                if invalid_attack in referred_attacks:
                    referred_attacks.remove(invalid_attack)
        
                dispatcher.utter_message(text=("Sorry. I don't have any information about " + invalid_attack + " attack. [2]"))
                # print("Sorry. I don't have any information about " + invalid_attack + " attack. [2]")
        
        # list of valid attacks is empty 
        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        # remove duplicates
        referred_attacks= list(dict.fromkeys(referred_attacks))
        
        print("REFERRED ATTACKS (PREPROCESSED: " + str(referred_attacks))
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))
        

        # used for debugging in 'rasa interactive' mode
        if intent is None:
            dispatcher.utter_message(text="Sorry. I couldn't map your message to the rigth intent. Please rephrase your question including the attack name.")
            return [UserUtteranceReverted()]


        if intent == 'request_attack_information':
            # get requested information
            with open('json/attack_information.json') as json_file:
                data_dict = json.load(json_file)
                for valid_attack in referred_attacks:
                    if valid_attack in data_dict.keys():
                        characteristics = data_dict[valid_attack]["characteristics"]
                        dispatcher.utter_message(text=characteristics)
                        continue
                        # return []
                    else:
                        for attack in data_dict.keys():
                            if valid_attack in data_dict[attack]["subtypes"].keys():
                                characteristics = data_dict[attack]["subtypes"][valid_attack]["characteristics"]
                                dispatcher.utter_message(text=characteristics)
                                continue
                                # return []
                            else:
                                for subtype in data_dict[attack]["subtypes"].keys():
                                    # if subtypes has specific attacks 
                                    if "specific_attacks" in data_dict[attack]["subtypes"][subtype]:
                                        if valid_attack in data_dict[attack]["subtypes"][subtype]["specific_attacks"].keys():
                                            referred_attack_description = data_dict[attack]["subtypes"][subtype]["specific_attacks"][valid_attack]
                                            dispatcher.utter_message(text=referred_attack_description)
                                            continue
                                            # return []
                                        else:
                                            continue
                                            # dispatcher.utter_message(text=("Sorry. I don't have any information about that. [3]"))
                                            # return []
                                    else:
                                        continue

                                        # dispatcher.utter_message(text=("Sorry. I don't have any information about " + valid_attack + " attack [4]"))    
                                        # return []
                return [SlotSet("attack_information", referred_attacks)]
        elif intent == 'request_further_attack_classification':
            # get requested information
            with open('json/attack_information.json') as json_file:
                data_dict = json.load(json_file)
                attacks_subtypes = []
                for valid_attack in referred_attacks:
                    # e.g. subtypes of ddos attack
                    if valid_attack in data_dict.keys():
                        main_attack = ""
                        for subform in data_dict[valid_attack]['subtypes'].keys():
                            if not main_attack:
                                main_attack = valid_attack
                                dispatcher.utter_message(text="Subform(s) of " + main_attack + ":")
                            # TODO: attack characteristic should start with attack name!
                            subform_characteristics = data_dict[valid_attack]["subtypes"][subform]["characteristics"]
                            dispatcher.utter_message(text=subform + ": " + subform_characteristics)
                            attacks_subtypes.append(subform)

                        # return []
                    else:
                        # subtypes of subtypes --> specific attacks e.g. SYN Flood
                        for attack in data_dict.keys():
                            # requested attack is a subtype of a main attack
                            if valid_attack in data_dict[attack]["subtypes"].keys():
                                # if this subtype has specific attack information e.g. SYN flood
                                if "specific_attacks" in data_dict[attack]["subtypes"][valid_attack]:
                                    main_attack = ""
                                    for specific_attack in data_dict[attack]["subtypes"][valid_attack]["specific_attacks"].keys():
                                        if not main_attack:
                                            main_attack = valid_attack
                                            dispatcher.utter_message(text= "Specific attack(s) of " + main_attack + " attack:")
                                        specific_attack_characteristics = data_dict[attack]["subtypes"][valid_attack]["specific_attacks"][specific_attack]
                                        dispatcher.utter_message(text=specific_attack + ": " + specific_attack_characteristics)
                                        attacks_subtypes.append(specific_attack)
                                    # return []
                                else:
                                    dispatcher.utter_message(text="Sorry. I don't have more information about further subtypes")
                                    # return []
                            else:
                                for subtype_attack in data_dict[attack]["subtypes"].keys():
                                    if "specific_attacks" in data_dict[attack]["subtypes"][subtype_attack]:
                                        if valid_attack in data_dict[attack]["subtypes"][subtype_attack]["specific_attacks"]:
                                            dispatcher.utter_message(text="Sorry, I don't have further subtypes of " + valid_attack + " attack.")
                                
                if attacks_subtypes:
                    return [SlotSet("further_attack_classification", attacks_subtypes)]
                else:
                    return [SlotSet("further_attack_classification", None)]

    def __get_referred_attacks(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]):
        
        referred_attacks = []
        
        self.debug_tracker(tracker, dispatcher, domain)

        # get all entities from last user message
        entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(entities))
        
        # returns list e.g. ['ddos']
        attack_name = tracker.get_slot("attack_name")
        attack_type = tracker.get_slot("attack_type")
        identified_attack = tracker.get_slot("identified_attack")
        print("attack_name: " + str(attack_name) + " type: " + str(type(attack_name)))
        print("attack_type: " + str(attack_type) + " type: " + str(type(attack_type)))
        if identified_attack is not None:
            print("identified_attack: " + str(identified_attack))

        if len(entities) == 0:
            # get last executed action
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and identified_attack is not None:
                identified_attack_lower_case = identified_attack.lower()
                referred_attacks.append(identified_attack_lower_case)
                print("added identified attack '" + identified_attack_lower_case + "' to referred_attacks")
            
            else:
                # there was at least one slot set during conversation
                if tracker.get_last_event_for("slot") is None:
                    return False

                # elif last_executed_action["name"] == "action_provide_requested_attack_information":
                #     last_slot_set = tracker.get_last_event_for("slot")
                #     if last_slot_set["name"] in ["further_attack_classification", "attack_information"]:
                #         referred_attacks.extend(last_slot_set["value"])
                
                elif last_executed_action["name"] == "action_provide_requested_attack_information":
                    last_slot_set = tracker.get_last_event_for("slot")
                    skip = 0
                    while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    referred_attacks.extend(last_slot_set["value"])
                
                elif last_executed_action["name"] == "action_provide_attack_comparison":
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                    skip = 0
                    while last_slot_set["name"] != "compared_attacks":
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    
                    referred_attacks.extend(last_slot_set["value"])
                
                elif last_executed_action["name"] == "action_provide_attack_challenges":
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                    skip = 0
                    while last_slot_set["name"] != "attack_challenges":
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    
                    referred_attacks.extend(last_slot_set["value"])    

                elif last_executed_action["name"] == "action_provide_attack_impacts":
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                    skip = 0
                    while last_slot_set["name"] != "attack_impacts":
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    
                    referred_attacks.extend(last_slot_set["value"])

                elif last_executed_action["name"] == "action_provide_attack_symptoms":
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                    skip = 0
                    while last_slot_set["name"] != "attack_symptoms":
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    
                    referred_attacks.extend(last_slot_set["value"])  
                
                elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                    skip = 0
                    while last_slot_set["name"] != "attack_countermeasures":
                        skip += 1
                        last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                    
                    referred_attacks.extend(last_slot_set["value"])
            
        else:

            ####################################################################
            #                       DEBUGGING                                  #
            second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
            if second_last_user_utterance is not None:
                second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
                print("SECOND LAST user utterance: " + str(second_last_user_utterance))
                print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))

            third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
            if third_last_user_utterance is not None:
                third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
                print("THIRD LAST user utterance: " + str(third_last_user_utterance))
                print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))


            ######################################################################
            
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))

            entities_to_process = []
            entities_to_process.extend(converted_entity_values_attack_name)
            entities_to_process.extend(converted_entity_values_attack_type)
            print("ENTITIES TO PROCESS: " + str(entities_to_process))

            if len(entities_to_process) == 0:
                dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                return False
            else:
                for entity_value in entities_to_process:
                    referred_attacks.append(entity_value)

        return referred_attacks

    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        latest_action = tracker.get_last_event_for("action", exclude=["action_listen"])
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
        latest_slot_event = tracker.get_last_event_for("slot")
        latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_event:
            print("LATEST SLOT EVENT: " + str(latest_slot_event) + ", TYPE: " + str(type(latest_slot_event)))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_event = tracker.get_last_event_for(event_type="slot", skip=1)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("SECOND LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_event:
            print("LATEST SLOT EVENT: " + str(second_latest_slot_event) + ", TYPE: " + str(type(second_latest_slot_event)))
        if second_latest_slot_set is not None:
            print("SECOND LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(second_latest_slot_set["value"]) + ", TYPE: " + str(type(second_latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")
    
    
    def __get_supported_attacks(self):

        main_attacks = []
        subtypes = []
        specific_examples = []

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
        
        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        return main_attacks

class ActionProvideAttackComparison(Action):

    def name(self) -> Text:
        return "action_provide_attack_comparison"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            
        supported_attacks = self.__get_supported_attacks()[0]
        attack_relationship_dict = self.__get_supported_attacks()[1]
        print("SUPPORTED ATTACKS: " + str(supported_attacks))
        print("ATTACK RELATIONSHIP: " + str(attack_relationship_dict))

        attacks_to_compare = self.__get_attacks_for_comparison(dispatcher, tracker, domain)

        if not attacks_to_compare:
            dispatcher.utter_message(text="Please be more specific. Rephrase your question including all attacks that should be compared.")
            # print("Please be more specific. Rephrase your question including all attacks that should be compared. [run]")
        if not attacks_to_compare:
            return [ActionReverted(),UserUtteranceReverted()]

        #requested attack
        print("ATTACKS TO COMPARE: " + str(attacks_to_compare))
        # if attack is not available in JSON file
        available_attacks = []
        unavailable_attacks = []
        for particular_attack in attacks_to_compare:
            if particular_attack in supported_attacks:
                available_attacks.append(particular_attack)
            else:
                unavailable_attacks.append(particular_attack)
                # dispatcher.utter_message(text=("Sorry. I don't have any information about that attack."))
                # return []

          # remove duplicates
        available_attacks= list(dict.fromkeys(available_attacks))

        if len(available_attacks) == 0 or len(available_attacks) == 1:
            dispatcher.utter_message(text="There are not enough valid attacks to make a comparison:")
            dispatcher.utter_message(text="Valid attacks (available in my DB): " + ", ".join(available_attacks))
            print("unsupported attacks: " + str(unavailable_attacks))
            self.__display_unavailable_attacks(unavailable_attacks, dispatcher)
            dispatcher.utter_message(text="Please rewrite your question again specifying all attacks.")
            return [UserUtteranceReverted()]

        if len(unavailable_attacks) > 0:
            dispatcher.utter_message(text="There were some unsupported attacks in your request, which won't be further processed:")
            self.__display_unavailable_attacks(unavailable_attacks, dispatcher)
        
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))

        #requested attack
        print("ATTACKS TO COMPARE (PREPROCESSED): " + str(attacks_to_compare))
        
        # used for debugging in 'rasa interactive' mode
        if intent is None:
            dispatcher.utter_message(text="Sorry. I couldn't map your message to the rigth intent. Please rephrase your question including the attack name.")
            return [UserUtteranceReverted()]
        
        ## Compare attacks
        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)


            # main attack vs main attack
            if self.__all_main_attacks(available_attacks, attack_relationship_dict):
                for particular_attack in available_attacks:
                    dispatcher.utter_message(text= data_dict[particular_attack]["characteristics"])
                # return []

            # handle subtypes only e.g. worm, virus, volumetric etc.
            elif self.__only_subtypes(available_attacks, attack_relationship_dict):
                self.__comparison_subtypes_attacks_only(available_attacks, attack_relationship_dict, data_dict, dispatcher)
                # return []

            # handle only specific attacks
            elif self.__only_specific_attack(available_attacks, attack_relationship_dict):
                self.__comparison_specific_attacks_only(available_attacks, attack_relationship_dict, data_dict, dispatcher)
                # return []
            
            # comparing subtypes with main types and vice versa
            else:
                divided_attacks_into_groups = self.__divide_attacks_into_groups(available_attacks, attack_relationship_dict)
                major_attack_list = divided_attacks_into_groups[0]
                subtype_attack_list = divided_attacks_into_groups[1]
                specific_attack_list = divided_attacks_into_groups[2]

                if len(major_attack_list) != 0:
                    for major_attack in major_attack_list:
                        description = data_dict[major_attack]["characteristics"]
                        dispatcher.utter_message(text=description)
                    
                    for remaining_attack in available_attacks:
                        if remaining_attack not in major_attack_list:
                            
                            # it's a subtype
                            if remaining_attack in subtype_attack_list:
                                parent = attack_relationship_dict[remaining_attack]["parent"]
                                description = data_dict[parent]["subtypes"][remaining_attack]["characteristics"]

                                dispatcher.utter_message(text=description)
                                if parent in major_attack_list:
                                    dispatcher.utter_message(text= "This attack is a subform of the previously explained " + parent + " attack")
                                else:
                                    dispatcher.utter_message(text= "This attack is a subform of: " + parent)
                            
                            # it's a specific example
                            if remaining_attack in specific_attack_list:
                                grandparent = attack_relationship_dict[remaining_attack]["grandparent"]
                                parent = attack_relationship_dict[remaining_attack]["parent"]
                                description = data_dict[grandparent]["subtypes"][parent]["specific_attacks"][remaining_attack]

                                dispatcher.utter_message(text=description)
                                dispatcher.utter_message(text= "This attack is a specific example of " + parent + ", which, in turn, belongs to the " + grandparent + " attacks.")

                else:
                    if len(subtype_attack_list) != 0:
                        for attack in subtype_attack_list:
                            parent = attack_relationship_dict[attack]["parent"]
                            description = data_dict[parent]["subtypes"][attack]["characteristics"]

                            dispatcher.utter_message(text=description)

                        for remaining_attack in available_attacks:
                            if remaining_attack in specific_attack_list:
                                grandparent = attack_relationship_dict[remaining_attack]["grandparent"]
                                parent = attack_relationship_dict[remaining_attack]["parent"]
                                description = data_dict[grandparent]["subtypes"][parent]["specific_attacks"][remaining_attack]

                                dispatcher.utter_message(text=description)
                                dispatcher.utter_message(text= "This attack is a specific example of " + parent + " attacks.")
                # return []
            
            return [SlotSet("compared_attacks", available_attacks)]

    def __display_unavailable_attacks(self, unsupported_attacks, dispatcher):
        if len(unsupported_attacks) == 1:
            dispatcher.utter_message(text="Invalid attacks (not in my DB): " + unsupported_attacks[0])
        elif len(unsupported_attacks) > 1:
            dispatcher.utter_message(text="Invalid attacks (not in my DB): " + ", ".join(unsupported_attacks))
    
    def __divide_attacks_into_groups(self, attack_list, attack_relationship_dict):

        major_attack_list = []
        subtype_attack_list = []
        specific_attack_list = []

        switcher = {
            "major_attack": major_attack_list.append,
            "subtype_attack": subtype_attack_list.append,
            "specific_attack": specific_attack_list.append
        }
        for attack in attack_list:
            attack_type = attack_relationship_dict[attack]["attack_type"]
            switcher[attack_type](attack)
        
        return [major_attack_list, subtype_attack_list, specific_attack_list]


    def __comparison_subtypes_attacks_only(self, attack_list, attack_relationship_dict, data_dict, dispatcher):
        
        # subtype vs subtype with mutual main attack
        if self.__mutual_parent(attack_list, attack_relationship_dict):
            
            # retrieve main attack
            attack = attack_relationship_dict[attack_list[0]]["parent"]

            for particular_attack in attack_list:
                difference = data_dict[attack]["subtypes"][particular_attack]["scope"]
                dispatcher.utter_message(text=particular_attack + ": " + difference)
            return
        
        # subtype vs subtype with different main attack
        else:
            for particular_attack in attack_list:

                # retrieve parent
                attack = attack_relationship_dict[particular_attack]["parent"]
                
                # retrieve attack description
                description = data_dict[attack]["subtypes"][particular_attack]["characteristics"]
                
                
                dispatcher.utter_message(text=description)
                dispatcher.utter_message(text="It is a subform of "  + attack + " attacks.")
            return

    def __comparison_specific_attacks_only(self, attack_list, attack_relationship_dict, data_dict, dispatcher):

        for particular_attack in attack_list:
            attack = attack_relationship_dict[particular_attack]["grandparent"]
            subtype = attack_relationship_dict[particular_attack]["parent"]

            # display attack description
            description = data_dict[attack]["subtypes"][subtype]["specific_attacks"][particular_attack]
            dispatcher.utter_message(text=description)
            if not self.__mutual_parent(attack_list, attack_relationship_dict):
                dispatcher.utter_message(text="It belongs to " + subtype + " " + attack + "attacks.")

        return


    def __mutual_parent(self, attack_list, attack_relationship_dict):
        parent = ""
        for particular_attack in attack_list:
            if not parent:
                parent = attack_relationship_dict[particular_attack]["parent"]
            else:
                if parent != attack_relationship_dict[particular_attack]["parent"]:
                    return False
        return True

    def __only_subtypes(self, attacks_to_check, attack_relationship_dict):

        for part_attack in attacks_to_check:
            if not self.__is_subtype_attack(part_attack, attack_relationship_dict):
                return False
        return True

    def __is_subtype_attack(self, attack_to_check, attack_relationship_dict):
        # return (("grandparent" not in attack_relationship_dict[attack_to_check].keys()) 
        #         and ("parent" in attack_relationship_dict[attack_to_check].keys()))

        return attack_relationship_dict[attack_to_check]["attack_type"] == "subtype_attack"

    def __only_specific_attack(self, attacks_to_check, attack_relationship_dict):
        
        for part_attack in attacks_to_check:
            if not self.__is_specific_attack(part_attack, attack_relationship_dict):
                return False
        return True

    def __is_specific_attack(self, attack_to_check, attack_relationship_dict):
        # return "grandparent" in attack_relationship_dict[attack_to_check].keys()

        return attack_relationship_dict[attack_to_check]["attack_type"] == "specific_attack"


    def __all_main_attacks(self, attack_list, attack_relationship_dict):
        
        # all_main_attacks = True
        for particular_attack in attack_list:
            # if "parent" not in attack_relationship_dict[particular_attack].keys():
            #   all_main_attacks = False
            #   break    
            if not attack_relationship_dict[particular_attack]["attack_type"] == "major_attack":
                return False
        
        # return all_main_attacks
        return True
    
    def __get_attacks_for_comparison(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]):
        
        attacks_to_compare = []
        
        # get all entities from last user message
        entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(entities))
        
        # returns list e.g. ['ddos']
        attack_names = tracker.get_slot("attack_name")
        attack_types = tracker.get_slot("attack_type")
        identified_attack = tracker.get_slot("identified_attack")

        print("ATTACK_NAMES: " + str(attack_names) + " Type: " + str(type(attack_names)))
        print("ATTACK_TYPES: " + str(attack_types) + " Type: " + str(type(attack_types)))
        if identified_attack is not None:
            print("IDENTIFIED_ATTACK: " + identified_attack + " Type: " + str(type(identified_attack)))

        ####################################################################
        #                       DEBUGGING                                  #
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        
        self.debug_tracker(tracker, dispatcher, domain)

        print("#                        DEBUGGING END                       ")
        print("#############################################################")
        ######################################################################

        # no entities in latest user message: e.g. 'whats the difference between them?'
        if len(entities) == 0:
            ''' 
            tracker.get_last_event_for() doesn't work if latest message includes entities,
            like "whats the difference to [syn flood]?". due to the auto slot mapping feature.
            Use for len(entities) > 0 tracker.get_slot()!
            '''
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            second_last_executed_action = tracker.get_last_event_for(event_type="action",  exclude=["action_listen"], skip=1)

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))

            if second_last_executed_action is not None:
                print("second last executed action using tracker method: " + str(second_last_executed_action) + str(type(second_last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and identified_attack is not None:
                attacks_to_compare.append(identified_attack)
            # if SecBot explained two attacks sequentially and the next user message
            # is for example "whats the difference between them?" --> e.g. worm vs. virus
            elif last_executed_action["name"] == 'action_provide_requested_attack_information':
                # get intent that led to this action (second last intent)
                second_last_user_utterance = tracker.get_last_event_for("user", exclude=["action_listen"], skip= 1)
                second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
                print("SECOND LAST INTENT: " + str(second_last_intent))
                
                if second_last_intent == 'request_attack_information':
                    entities_to_include_1 = second_last_user_utterance["parse_data"]["entities"]
                    if len(entities_to_include_1) != 0:
                        for entity_1 in entities_to_include_1:
                            if entity_1["entity"] in ["attack_name", "attack_type"]:
                                attacks_to_compare.append(entity_1["value"])
                    if second_last_executed_action["name"] == 'action_provide_requested_attack_information':
                        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
                        third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
                        print("THIRD LAST INTENT: " + str(third_last_intent))
                        if third_last_intent == 'request_attack_information':
                            entities_to_include_2 = third_last_user_utterance["parse_data"]["entities"]
                            if len(entities_to_include_2) != 0:
                                for entity_2 in entities_to_include_2:
                                    if entity_2["entity"] in ["attack_name", "attack_type"]:
                                        attacks_to_compare.append(entity_2["value"])
        
                    elif second_last_executed_action["name"] == "action_idattack" and identified_attack is not None:
                        print("identified_attack: " + str(identified_attack))
                        # all keys are are for comparisons in lower case
                        identified_attack_lower_case = identified_attack.lower()
                        attacks_to_compare.append(identified_attack_lower_case)
                    
                    elif second_last_executed_action["name"] == "action_provide_attack_challenges":
                        entities = tracker.get_slot("attack_challenges")
                        attacks_to_compare.extend(entities)
                    elif second_last_executed_action["name"] == "action_provide_attack_impacts":
                        entities = tracker.get_slot("attack_impacts")
                        attacks_to_compare.extend(entities)
                    elif second_last_executed_action["name"] == "action_provide_attack_symptoms":
                        entities = tracker.get_slot("attack_symptoms")
                        attacks_to_compare.extend(entities)
                    elif second_last_executed_action["name"] == "action_provide_attack_countermeasures":
                        entities = tracker.get_slot("attack_countermeasures")
                        attacks_to_compare.extend(entities)

                    print("attacks to compare 1: " + str(attacks_to_compare))
                # e.g. are there subforms of ddso? --> application layer, protocol based, volumetric
                # what are the differences? --> explain differences between them
                elif second_last_intent == 'request_further_attack_classification':

                    latest_further_attack_classification_slot_event = tracker.get_last_event_for("slot")
                    if latest_further_attack_classification_slot_event["name"] == "further_attack_classification":
                        latest_further_attack_classification = latest_further_attack_classification_slot_event["value"]
                        print("LATEST FURTHER ATTACK CLASSIFICATIONS: " + str(latest_further_attack_classification) + " TYPE: " + str(type(latest_further_attack_classification)))
                    
                        print("attacks to compare 2: " + str(attacks_to_compare))
                    if latest_further_attack_classification is not None:
                        for specific_attack in latest_further_attack_classification:
                            attacks_to_compare.append(specific_attack)

                        print("attacks to compare 3: " + str(attacks_to_compare))

                    further_attack_classification = tracker.get_slot("further_attack_classification")
                    if further_attack_classification is not None:
                        print("LATEST FURTHER ATTACK CLASSIFICATIONS using get.slot() method: " + str(further_attack_classification) + " TYPE: " + str(type(further_attack_classification)))

                        print("attacks to compare 4: " + str(attacks_to_compare))

            elif last_executed_action["name"] == "action_provide_attack_challenges":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_challenges":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])    

            elif last_executed_action["name"] == "action_provide_attack_impacts":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_impacts":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_countermeasures":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_symptoms":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_symptoms":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])  
                
                print("attacks to compare 8: " + str(attacks_to_compare))
                
            else:
                # dispatcher.utter_message(text="Please be more specific in your request. Rephrase your question including all attacks")
                print("attacks to compare 9: " + str(attacks_to_compare))
                return False


        elif len(entities) == 1:
            # retrieve latest entity in latest user message
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))
            
            # should be only 1 entity in entity_values_from_latest_message
            entity_values_from_latest_message = []
            entity_values_from_latest_message.extend(converted_entity_values_attack_name)
            entity_values_from_latest_message.extend(converted_entity_values_attack_type)

            if len(entity_values_from_latest_message) != 0:
                for entity_value in entity_values_from_latest_message:
                    attacks_to_compare.append(entity_value)
            print("attacks to compare 10: " + str(attacks_to_compare))

            self.debug_tracker(tracker, dispatcher, domain)
            # retrieve entity / entities from previous user message 
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            
            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            print("attacks to compare 11: " + str(attacks_to_compare))

            if last_executed_action["name"] == "action_provide_requested_attack_information":

                second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
                second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
                print("SECOND LAST INTENT: " + str(second_last_intent))

                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                if (last_slot_set["name"] == "further_attack_classification" and 
                    tracker.get_slot("further_attack_classification") is not None):
                        attacks_to_compare.extend(last_slot_set["value"])
                
                if last_slot_set["name"] == "attack_information":
                    attacks_to_compare.extend(last_slot_set["value"])
                
                # explained_entities = second_last_user_utterance["parse_data"]["entities"]
                # last_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
                # print("LAST SLOT SET: " + str(last_slot_set["name"]) + str(last_slot_set["value"]) + ", type: " + str(type(last_slot_set["value"])))

                # latest_further_attack_classification = tracker.get_slot("further_attack_classification")
                # print("LATEST FURTHER ATTACK IDENTIFICATION values: " + str(latest_further_attack_classification))
                # if second_last_intent == "request_further_attack_classification":
                #     # attack_relationship_dict = self.__get_supported_attacks()[1]
                #     # see scenario 2 in notes
                #     if len(explained_entities) != 0 and latest_further_attack_classification is not None:
                #         print("attacks to compare 12: " + str(attacks_to_compare))
                #         dispatcher.utter_message(text="It is not clear which attacks do you want to compare (with subtypes or their major attack?)")
                #         return False   
                #     else:
                #         if latest_further_attack_classification is not None:
                #             attacks_to_compare.extend(latest_further_attack_classification)   
                #         print("attacks to compare 13: " + str(attacks_to_compare))
            
            elif last_executed_action["name"] == "action_idattack" and tracker.get_slot("identified_attack") is not None:
                identified_attack_lower_case = tracker.get_slot("identified_attack").lower()
                attacks_to_compare.append(identified_attack_lower_case)
                print("attacks to compare 14: " + str(attacks_to_compare))
            
            elif last_executed_action["name"] == "action_provide_attack_challenges":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_challenges":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])    

            elif last_executed_action["name"] == "action_provide_attack_impacts":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_impacts":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_countermeasures":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_symptoms":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_symptoms":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                attacks_to_compare.extend(last_slot_set["value"])  
                
                print("attacks to compare 8: " + str(attacks_to_compare))
        
        else:
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))
            
            ####################################################################
            #                       DEBUGGING                                  #
            # second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
            # second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            # print("SECOND LAST user utterance: " + str(second_last_user_utterance))

            # third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
            # second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            # print("THIRD LAST user utterance: " + str(third_last_user_utterance))

            self.debug_tracker(tracker, dispatcher, domain)
            ######################################################################
            # get latest entity values from last user message
            if len(converted_entity_values_attack_name) == 0:
                if len(converted_entity_values_attack_type) == 0:
                    print("attacks to compare 15: " + str(attacks_to_compare))
                    # there are entities in last message but not the required ones
                    dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                    return False
                else:
                    for each_attack_type in converted_entity_values_attack_type:
                        attacks_to_compare.append(each_attack_type)
                    print("attacks to compare 16: " + str(attacks_to_compare))
            else:
                for each_attack in converted_entity_values_attack_name:
                    attacks_to_compare.append(each_attack)
                if len(converted_entity_values_attack_type) != 0:
                    for each_attack_type in converted_entity_values_attack_type:
                        attacks_to_compare.append(each_attack_type)
                print("attacks to compare 17: " + str(attacks_to_compare))
        return attacks_to_compare
    
   
    def __get_supported_attacks(self):
        ''' Returns a tuple including list of all supported attacks,
            as well as a nested dict specifying relations btw attacks.
            
            relation_dict = {'syn flood': {'parent': 'protocol based',
                                            'grandparent': 'ddos'
                                            'attack_type': 'specific_attack'}}
            
             '''

        main_attacks = []
        subtypes = []
        specific_examples = []

        attack_relation_dict = {}

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            # print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                
                # store main attack and its subtypes in attack_relation_dict
                # e.g {'ddos':{'childre': ['volumetric', 'application layer', 'protocol based']}}
                # temp_dict = {}
                # children = data_dict[major_attack].keys()
                # temp_dict["children"] = children
                # attack_relation_dict["children"] = temp_dict
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                grandchildren = []
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)

                    temp_specific_attack_list = []
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
                            temp_specific_attack_list.append(particular_example)

                            # create relations of specific attack
                            temp_dict_particular_example = {}
                            temp_dict_particular_example["parent"] = sub_attack
                            temp_dict_particular_example["grandparent"] = attack
                            temp_dict_particular_example["attack_type"] = "specific_attack"

                            # add relations of specific attack
                            attack_relation_dict[particular_example] = temp_dict_particular_example
                    
                    # create relations of subattack 
                    temp_dict_sub_attack = {}
                    temp_dict_sub_attack["children"] = temp_specific_attack_list
                    grandchildren.extend(temp_specific_attack_list)
                    
                    temp_dict_sub_attack["parent"] = attack
                    temp_dict_sub_attack["attack_type"] = "subtype_attack"
                    
                    # add relations of subattack
                    attack_relation_dict[sub_attack] = temp_dict_sub_attack

                temp_dict_attack = {}
                temp_dict_attack["children"] = subtype_attacks
                temp_dict_attack["grandchildren"] = grandchildren
                temp_dict_attack["attack_type"] = "major_attack"

                attack_relation_dict[attack] = temp_dict_attack

        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        # print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        # print("ATTACK RELATIONSHIPS: " + str(attack_relation_dict))

        # return a tuple
        return (main_attacks, attack_relation_dict)
    
    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")

        exclude_action = ["action_listen", "utter_chitchat", "utter_out_of_scope"]
        exclude_user = ["chitchat", "out_of_scope"]
        exclude_slot = ["attack_name", "attack_type", "problem", "target"]

        latest_action = tracker.get_last_event_for("action", exclude=exclude_action)
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=exclude_user, skip= 1)
        latest_slot_event = tracker.get_last_event_for("slot")
        latest_slot_set = tracker.get_last_event_for("slot", exclude=exclude_slot, skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_event:
            print("LATEST SLOT EVENT: " + str(latest_slot_event) + ", TYPE: " + str(type(latest_slot_event)))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_event = tracker.get_last_event_for(event_type="slot", skip=1)
        # second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("SECOND LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_event:
            print("LATEST SLOT EVENT: " + str(second_latest_slot_event) + ", TYPE: " + str(type(second_latest_slot_event)))
        if second_latest_slot_set is not None:
            print("SECOND LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")

class ActionProvideAttackChallenges(Action):

    def name(self) -> Text:
        return "action_provide_attack_challenges"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        supported_attacks = self.__get_supported_attacks()[0]
        attack_relationship_dict = self.__get_supported_attacks()[1]

        referred_attacks = self.__get_attacks_for_challenge_description(dispatcher, tracker, domain)

        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        #requested attacks
        print(str(referred_attacks))
        
        # remove attacks that are not covered in 'attack_information.json'
        referred_attacks = self.__remove_invalid_attacks(referred_attacks, supported_attacks, dispatcher)
        
        # list of valid attacks is empty 
        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        # remove duplicates
        referred_attacks= list(dict.fromkeys(referred_attacks))

        print("REFERRED ATTACKS (PREPROCESSED: " + str(referred_attacks))
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            for attack in referred_attacks:
                if attack_relationship_dict[attack]["attack_type"] == 'major_attack':
                    challenges = data_dict[attack]["challenges"]
                    dispatcher.utter_message(text=challenges)
                elif attack_relationship_dict[attack]["attack_type"] == 'subtype_attack':
                    parent = attack_relationship_dict[attack]["parent"]
                    challenges = data_dict[parent]["subtypes"][attack]["challenges"]
                    dispatcher.utter_message(text=challenges)
                elif attack_relationship_dict[attack]["attack_type"] == 'specific_attack':
                    parent = attack_relationship_dict[attack]["parent"]
                    grandparent = attack_relationship_dict[attack]["grandparent"]
                    challenges_parent = data_dict[grandparent]["subtypes"][parent]["challenges"]

                    dispatcher.utter_message(text= attack + " belongs to the attack group of " + parent + ".")
                    dispatcher.utter_message(text=challenges_parent)
                    # dispatcher.utter_message(text="Sorry, I don't have information about challenges of " + attack + " attack in my database.")

            return [SlotSet("attack_challenges", referred_attacks)]

    def __get_attacks_for_challenge_description(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]):

        referred_attacks = []
        
        self.debug_tracker(tracker, dispatcher, domain)

        # get all entities from last user message
        latest_entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(latest_entities))

        if len(latest_entities) == 0:
             # get last executed action
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            
            self.debug_tracker(tracker, dispatcher, domain)

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and tracker.get_slot("identified_attack") is not None:
                identified_attack_lower_case = tracker.get_slot("identified_attack").lower()
                referred_attacks.append(identified_attack_lower_case)
                print("added identified attack '" + identified_attack_lower_case + "' to referred_attacks")
            
            elif last_executed_action["name"] == "action_provide_requested_attack_information":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                if (last_slot_set["name"] == "further_attack_classification" and 
                    tracker.get_slot("further_attack_classification") is not None):
                        referred_attacks.extend(last_slot_set["value"])
                
                if last_slot_set["name"] == "attack_information":
                    referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_comparison":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "compared_attacks":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_impacts":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_impacts":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"]) 
            
            elif last_executed_action["name"] == "action_provide_attack_symptoms":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_symptoms":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"]) 

            elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_countermeasures":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"]) 
        
        else:
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))

            entities_to_process = []
            entities_to_process.extend(converted_entity_values_attack_name)
            entities_to_process.extend(converted_entity_values_attack_type)
            print("ENTITIES TO PROCESS: " + str(entities_to_process))

            # check if list of relevant entities is not empty
            if len(entities_to_process) == 0:
                dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                return False
            else:
                for entity_value in entities_to_process:
                    referred_attacks.append(entity_value)

        return referred_attacks

    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        latest_action = tracker.get_last_event_for("action", exclude=["action_listen"])
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
        latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")

    def __get_supported_attacks(self):
        ''' Returns a tuple including list of all supported attacks,
            as well as a nested dict specifying relations btw attacks. '''

        main_attacks = []
        subtypes = []
        specific_examples = []

        attack_relation_dict = {}

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            # print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                
                # store main attack and its subtypes in attack_relation_dict
                # e.g {'ddos':{'children': ['volumetric', 'application layer', 'protocol based']}}
                # temp_dict = {}
                # children = data_dict[major_attack].keys()
                # temp_dict["children"] = children
                # attack_relation_dict["children"] = temp_dict
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                grandchildren = []
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)

                    temp_specific_attack_list = []
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
                            temp_specific_attack_list.append(particular_example)

                            # create relations of specific attack
                            temp_dict_particular_example = {}
                            temp_dict_particular_example["parent"] = sub_attack
                            temp_dict_particular_example["grandparent"] = attack
                            temp_dict_particular_example["attack_type"] = "specific_attack"

                            # add relations of specific attack
                            attack_relation_dict[particular_example] = temp_dict_particular_example
                    
                    # create relations of subattack 
                    temp_dict_sub_attack = {}
                    temp_dict_sub_attack["children"] = temp_specific_attack_list
                    grandchildren.extend(temp_specific_attack_list)
                    
                    temp_dict_sub_attack["parent"] = attack
                    temp_dict_sub_attack["attack_type"] = "subtype_attack"
                    
                    # add relations of subattack
                    attack_relation_dict[sub_attack] = temp_dict_sub_attack

                temp_dict_attack = {}
                temp_dict_attack["children"] = subtype_attacks
                temp_dict_attack["grandchildren"] = grandchildren
                temp_dict_attack["attack_type"] = "major_attack"

                attack_relation_dict[attack] = temp_dict_attack

        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        # print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        # print("ATTACK RELATIONSHIPS: " + str(attack_relation_dict))

        # return a tuple
        return (main_attacks, attack_relation_dict)

    def __remove_invalid_attacks(self, attack_list, supported_attacks, dispatcher):
        invalid_attacks = []
        for attack in attack_list:
            if attack not in supported_attacks:
                invalid_attacks.append(attack)

        # remove attacks which are not covered in JSON file
        if len(invalid_attacks) != 0:
            for invalid_attack in invalid_attacks:
                if invalid_attack in attack_list:
                    attack_list.remove(invalid_attack)
        
                dispatcher.utter_message(text=("Sorry. I don't have any information about " + invalid_attack + " attack."))
        
        return attack_list

class ActionProvideAttackImpacts(Action):

    def name(self) -> Text:
        return "action_provide_attack_impacts"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        supported_attacks = self.__get_supported_attacks()[0]
        attack_relationship_dict = self.__get_supported_attacks()[1]

        referred_attacks = self.__get_attacks_for_impacts_description(dispatcher, tracker, domain)

        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        #requested attacks
        print(str(referred_attacks))
        
        # remove attacks that are not covered in 'attack_information.json'
        referred_attacks = self.__remove_invalid_attacks(referred_attacks, supported_attacks, dispatcher)
        
        # list of valid attacks is empty 
        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        # remove duplicates
        referred_attacks= list(dict.fromkeys(referred_attacks))

        print("REFERRED ATTACKS (PREPROCESSED: " + str(referred_attacks))
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            attachments_dict = {
                'ddos': "https://1drv.ms/b/s!AvrjnnB8WaSCwDnhXuPGBE8DmU7n?e=cDtwgn",
                'malware': "malware_impacts.pdf",
                'phishing': "phishing_impacts.pdf"
            }

            for attack in referred_attacks:
                if attack_relationship_dict[attack]["attack_type"] == 'major_attack':
                    impacts = data_dict[attack]["impacts"]
                    random_impact = random.choice(impacts)
                    dispatcher.utter_message(text="There exist various impacts for " + attack + " attacks. One such impact is the following: ")
                    dispatcher.utter_message(text=random_impact)
                    dispatcher.utter_message(text="There are many more impacts to describe. Please check out the following attachment for more information!")
                    dispatcher.utter_message(attachment=attachments_dict[attack])

                elif attack_relationship_dict[attack]["attack_type"] == 'subtype_attack':
                    parent = attack_relationship_dict[attack]["parent"]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + parent + 
                                            " attacks. Since there are many possible impacts to list, please check out the following attachment!")
                    dispatcher.utter_message(attachment=attachments_dict[parent])
                elif attack_relationship_dict[attack]["attack_type"] == 'specific_attack':
                    grandparent = attack_relationship_dict[attack]["grandparent"]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + grandparent + 
                                            " attacks. Since there are many possible impacts to list, please check out the following attachment!")
                    dispatcher.utter_message(attachment=attachments_dict[grandparent])
            return [SlotSet("attack_impacts", referred_attacks)]

    def __get_attacks_for_impacts_description(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]):

        referred_attacks = []
        
        self.debug_tracker(tracker, dispatcher, domain)

        # get all entities from last user message
        latest_entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(latest_entities))

        if len(latest_entities) == 0:
             # get last executed action
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            
            self.debug_tracker(tracker, dispatcher, domain)

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and tracker.get_slot("identified_attack") is not None:
                identified_attack_lower_case = tracker.get_slot("identified_attack").lower()
                referred_attacks.append(identified_attack_lower_case)
                print("added identified attack '" + identified_attack_lower_case + "' to referred_attacks")
            
            elif last_executed_action["name"] == "action_provide_requested_attack_information":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                if (last_slot_set["name"] == "further_attack_classification" and 
                    tracker.get_slot("further_attack_classification") is not None):
                        referred_attacks.extend(last_slot_set["value"])
                
                if last_slot_set["name"] == "attack_information":
                    referred_attacks.extend(last_slot_set["value"])
                    
            
            elif last_executed_action["name"] == "action_provide_attack_comparison":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "compared_attacks":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_challenges":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_challenges":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_symptoms":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_symptoms":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])

            elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_countermeasures":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])        
        else:
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))

            entities_to_process = []
            entities_to_process.extend(converted_entity_values_attack_name)
            entities_to_process.extend(converted_entity_values_attack_type)
            print("ENTITIES TO PROCESS: " + str(entities_to_process))

            # check if list of relevant entities is not empty
            if len(entities_to_process) == 0:
                dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                return False
            else:
                for entity_value in entities_to_process:
                    referred_attacks.append(entity_value)

        return referred_attacks

    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        latest_action = tracker.get_last_event_for("action", exclude=["action_listen"])
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
        latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")

    def __get_supported_attacks(self):
        ''' Returns a tuple including list of all supported attacks,
            as well as a nested dict specifying relations btw attacks. '''

        main_attacks = []
        subtypes = []
        specific_examples = []

        attack_relation_dict = {}

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            # print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                
                # store main attack and its subtypes in attack_relation_dict
                # e.g {'ddos':{'children': ['volumetric', 'application layer', 'protocol based']}}
                # temp_dict = {}
                # children = data_dict[major_attack].keys()
                # temp_dict["children"] = children
                # attack_relation_dict["children"] = temp_dict
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                grandchildren = []
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)

                    temp_specific_attack_list = []
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
                            temp_specific_attack_list.append(particular_example)

                            # create relations of specific attack
                            temp_dict_particular_example = {}
                            temp_dict_particular_example["parent"] = sub_attack
                            temp_dict_particular_example["grandparent"] = attack
                            temp_dict_particular_example["attack_type"] = "specific_attack"

                            # add relations of specific attack
                            attack_relation_dict[particular_example] = temp_dict_particular_example
                    
                    # create relations of subattack 
                    temp_dict_sub_attack = {}
                    temp_dict_sub_attack["children"] = temp_specific_attack_list
                    grandchildren.extend(temp_specific_attack_list)
                    
                    temp_dict_sub_attack["parent"] = attack
                    temp_dict_sub_attack["attack_type"] = "subtype_attack"
                    
                    # add relations of subattack
                    attack_relation_dict[sub_attack] = temp_dict_sub_attack

                temp_dict_attack = {}
                temp_dict_attack["children"] = subtype_attacks
                temp_dict_attack["grandchildren"] = grandchildren
                temp_dict_attack["attack_type"] = "major_attack"

                attack_relation_dict[attack] = temp_dict_attack

        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        # print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        # print("ATTACK RELATIONSHIPS: " + str(attack_relation_dict))

        # return a tuple
        return (main_attacks, attack_relation_dict)

    def __remove_invalid_attacks(self, attack_list, supported_attacks, dispatcher):
        invalid_attacks = []
        for attack in attack_list:
            if attack not in supported_attacks:
                invalid_attacks.append(attack)

        # remove attacks which are not covered in JSON file
        if len(invalid_attacks) != 0:
            for invalid_attack in invalid_attacks:
                if invalid_attack in attack_list:
                    attack_list.remove(invalid_attack)
        
                dispatcher.utter_message(text=("Sorry. I don't have any information about " + invalid_attack + " attack."))
        
        return attack_list         

class ActionProvideAttackSymptoms(Action):

    def name(self) -> Text:
        return "action_provide_attack_symptoms"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        supported_attacks = self.__get_supported_attacks()[0]
        attack_relationship_dict = self.__get_supported_attacks()[1]

        referred_attacks = self.__get_attacks_for_symptoms_description(dispatcher, tracker, domain)

        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        #requested attacks
        print(str(referred_attacks))
        
        # remove attacks that are not covered in 'attack_information.json'
        referred_attacks = self.__remove_invalid_attacks(referred_attacks, supported_attacks, dispatcher)
        
        # list of valid attacks is empty 
        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        # remove duplicates
        referred_attacks= list(dict.fromkeys(referred_attacks))

        print("REFERRED ATTACKS (PREPROCESSED: " + str(referred_attacks))
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))

        with open('json/symptoms.json') as json_file:
            data_dict = json.load(json_file)

            
            for attack in referred_attacks:
                if attack_relationship_dict[attack]["attack_type"] == 'major_attack':
                    attack_symptoms = data_dict[attack]
                    dispatcher.utter_message(text="See in the following the symptoms of " + attack + "attack:")
                    dispatcher.utter_message(text="\n".join(attack_symptoms))
                    
                elif attack_relationship_dict[attack]["attack_type"] == 'subtype_attack':
                    parent = attack_relationship_dict[attack]["parent"]
                    attack_symptoms = data_dict[parent]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + parent + 
                                            " attacks. See below possible symptoms of " + parent + " attacks:")
                    dispatcher.utter_message(text="\n".join(attack_symptoms))

                elif attack_relationship_dict[attack]["attack_type"] == 'specific_attack':
                    grandparent = attack_relationship_dict[attack]["grandparent"]
                    attack_symptoms = data_dict[grandparent]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + grandparent + 
                                            " attacks. See below possible symptoms of " + grandparent + " attacks:")
                    dispatcher.utter_message(text="\n".join(attack_symptoms))
            return [SlotSet("attack_symptoms", referred_attacks)]

    def __get_attacks_for_symptoms_description(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]):

        referred_attacks = []
        
        self.debug_tracker(tracker, dispatcher, domain)

        # get all entities from last user message
        latest_entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(latest_entities))

        if len(latest_entities) == 0:
             # get last executed action
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            
            self.debug_tracker(tracker, dispatcher, domain)

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and tracker.get_slot("identified_attack") is not None:
                identified_attack_lower_case = tracker.get_slot("identified_attack").lower()
                referred_attacks.append(identified_attack_lower_case)
                print("added identified attack '" + identified_attack_lower_case + "' to referred_attacks")
            
            elif last_executed_action["name"] == "action_provide_requested_attack_information":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                if (last_slot_set["name"] == "further_attack_classification" and 
                    tracker.get_slot("further_attack_classification") is not None):
                        referred_attacks.extend(last_slot_set["value"])
                
                if last_slot_set["name"] == "attack_information":
                    referred_attacks.extend(last_slot_set["value"])
                    
            
            elif last_executed_action["name"] == "action_provide_attack_comparison":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "compared_attacks":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_challenges":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_challenges":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])    

            elif last_executed_action["name"] == "action_provide_attack_impacts":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_impacts":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_countermeasures":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_countermeasures":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])

        else:
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))

            entities_to_process = []
            entities_to_process.extend(converted_entity_values_attack_name)
            entities_to_process.extend(converted_entity_values_attack_type)
            print("ENTITIES TO PROCESS: " + str(entities_to_process))

            # check if list of relevant entities is not empty
            if len(entities_to_process) == 0:
                dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                return False
            else:
                for entity_value in entities_to_process:
                    referred_attacks.append(entity_value)

        return referred_attacks

    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        latest_action = tracker.get_last_event_for("action", exclude=["action_listen"])
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
        latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")

    def __get_supported_attacks(self):
        ''' Returns a tuple including list of all supported attacks,
            as well as a nested dict specifying relations btw attacks. '''

        main_attacks = []
        subtypes = []
        specific_examples = []

        attack_relation_dict = {}

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            # print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                
                # store main attack and its subtypes in attack_relation_dict
                # e.g {'ddos':{'children': ['volumetric', 'application layer', 'protocol based']}}
                # temp_dict = {}
                # children = data_dict[major_attack].keys()
                # temp_dict["children"] = children
                # attack_relation_dict["children"] = temp_dict
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                grandchildren = []
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)

                    temp_specific_attack_list = []
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
                            temp_specific_attack_list.append(particular_example)

                            # create relations of specific attack
                            temp_dict_particular_example = {}
                            temp_dict_particular_example["parent"] = sub_attack
                            temp_dict_particular_example["grandparent"] = attack
                            temp_dict_particular_example["attack_type"] = "specific_attack"

                            # add relations of specific attack
                            attack_relation_dict[particular_example] = temp_dict_particular_example
                    
                    # create relations of subattack 
                    temp_dict_sub_attack = {}
                    temp_dict_sub_attack["children"] = temp_specific_attack_list
                    grandchildren.extend(temp_specific_attack_list)
                    
                    temp_dict_sub_attack["parent"] = attack
                    temp_dict_sub_attack["attack_type"] = "subtype_attack"
                    
                    # add relations of subattack
                    attack_relation_dict[sub_attack] = temp_dict_sub_attack

                temp_dict_attack = {}
                temp_dict_attack["children"] = subtype_attacks
                temp_dict_attack["grandchildren"] = grandchildren
                temp_dict_attack["attack_type"] = "major_attack"

                attack_relation_dict[attack] = temp_dict_attack

        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        # print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        # print("ATTACK RELATIONSHIPS: " + str(attack_relation_dict))

        # return a tuple
        return (main_attacks, attack_relation_dict)

    def __remove_invalid_attacks(self, attack_list, supported_attacks, dispatcher):
        invalid_attacks = []
        for attack in attack_list:
            if attack not in supported_attacks:
                invalid_attacks.append(attack)

        # remove attacks which are not covered in JSON file
        if len(invalid_attacks) != 0:
            for invalid_attack in invalid_attacks:
                if invalid_attack in attack_list:
                    attack_list.remove(invalid_attack)
        
                dispatcher.utter_message(text=("Sorry. I don't have any information about " + invalid_attack + " attack."))
        
        return attack_list 
    
class ActionProvideAttackCountermeasures(Action):

    def name(self) -> Text:
        return "action_provide_attack_countermeasures"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        supported_attacks = self.__get_supported_attacks()[0]
        attack_relationship_dict = self.__get_supported_attacks()[1]

        referred_attacks = self.__get_attacks_for_countermeasures_description(dispatcher, tracker, domain)

        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        #requested attacks
        print(str(referred_attacks))
        
        # remove attacks that are not covered in 'attack_information.json'
        referred_attacks = self.__remove_invalid_attacks(referred_attacks, supported_attacks, dispatcher)
        
        # list of valid attacks is empty 
        if not referred_attacks:
            dispatcher.utter_message(text="Be more specific. Please rephrase and include the attack(s) you are interested in.")
            return [UserUtteranceReverted()]
        
        # remove duplicates
        referred_attacks= list(dict.fromkeys(referred_attacks))

        print("REFERRED ATTACKS (PREPROCESSED: " + str(referred_attacks))
        intent = tracker.get_intent_of_latest_message()
        print("CURRENT INTENT: " + str(intent) + ". TYPE: " + str(type(intent)))

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            
            for attack in referred_attacks:
                if attack_relationship_dict[attack]["attack_type"] == 'major_attack':
                    attack_countermeasures = data_dict[attack]["countermeasures"]
                    dispatcher.utter_message(text="See in the following possible countermeasures of " + attack + " attacks:")
                    dispatcher.utter_message(text="\n".join(attack_countermeasures))

                elif attack_relationship_dict[attack]["attack_type"] == 'subtype_attack':
                    parent = attack_relationship_dict[attack]["parent"]
                    attack_countermeasures = data_dict[parent]["countermeasures"]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + parent + 
                                            " attacks. See below possible countermeasures of " + parent + " attacks:")
                    dispatcher.utter_message(text="\n".join(attack_countermeasures))
                elif attack_relationship_dict[attack]["attack_type"] == 'specific_attack':
                    grandparent = attack_relationship_dict[attack]["grandparent"]
                    attack_countermeasures = data_dict[grandparent]["countermeasures"]
                    dispatcher.utter_message(text="The " + attack + " attack belongs to the group of " + grandparent + 
                                            " attacks. See below possible countermeasures of " + grandparent + " attacks:")
                    dispatcher.utter_message(text="\n".join(attack_countermeasures))
            return [SlotSet("attack_countermeasures", referred_attacks)]

    def __get_attacks_for_countermeasures_description(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]):

        referred_attacks = []
        
        self.debug_tracker(tracker, dispatcher, domain)

        # get all entities from last user message
        latest_entities = tracker.latest_message.get("entities", [])
        print("LATEST ENTITIES: " + str(latest_entities))

        if len(latest_entities) == 0:
             # get last executed action
            last_executed_action = tracker.get_last_event_for(event_type="action", exclude=["action_listen"])
            
            self.debug_tracker(tracker, dispatcher, domain)

            if last_executed_action is not None:
                print("last executed action using tracker method: " + str(last_executed_action) + str(type(last_executed_action)))
            
            if last_executed_action["name"] == "action_idattack" and tracker.get_slot("identified_attack") is not None:
                identified_attack_lower_case = tracker.get_slot("identified_attack").lower()
                referred_attacks.append(identified_attack_lower_case)
                print("added identified attack '" + identified_attack_lower_case + "' to referred_attacks")
            
            elif last_executed_action["name"] == "action_provide_requested_attack_information":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] not in ["further_attack_classification", "attack_information"]:
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                if (last_slot_set["name"] == "further_attack_classification" and 
                    tracker.get_slot("further_attack_classification") is not None):
                        referred_attacks.extend(last_slot_set["value"])
                
                if last_slot_set["name"] == "attack_information":
                    referred_attacks.extend(last_slot_set["value"])
                    
            
            elif last_executed_action["name"] == "action_provide_attack_comparison":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "compared_attacks":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_challenges":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_challenges":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])    

            elif last_executed_action["name"] == "action_provide_attack_impacts":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_impacts":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
            
            elif last_executed_action["name"] == "action_provide_attack_symptoms":
                last_slot_set = tracker.get_last_event_for(event_type="slot", skip=0)
                skip = 0
                while last_slot_set["name"] != "attack_symptoms":
                    skip += 1
                    last_slot_set = tracker.get_last_event_for(event_type="slot", skip=skip)
                
                referred_attacks.extend(last_slot_set["value"])
        else:
            entity_values_attack_name = tracker.get_latest_entity_values("attack_name")
            converted_entity_values_attack_name = list(entity_values_attack_name)
            print("LATEST_ENTITY_VALUE_ATTACK_NAME" + str(converted_entity_values_attack_name))
            
            entity_values_attack_type = tracker.get_latest_entity_values("attack_type")
            converted_entity_values_attack_type = list(entity_values_attack_type)
            print("LATEST_ENTITY_VALUE_ATTACK_TYPE" + str(converted_entity_values_attack_type))

            entities_to_process = []
            entities_to_process.extend(converted_entity_values_attack_name)
            entities_to_process.extend(converted_entity_values_attack_type)
            print("ENTITIES TO PROCESS: " + str(entities_to_process))

            # check if list of relevant entities is not empty
            if len(entities_to_process) == 0:
                dispatcher.utter_message(text=("Sorry. I don't have any information about those attacks."))
                return False
            else:
                for entity_value in entities_to_process:
                    referred_attacks.append(entity_value)

        return referred_attacks

    def debug_tracker(self, tracker, dispatcher, domain):
        print("#############################################################")
        print("#                        DEBUGGING START                     #")
        latest_action = tracker.get_last_event_for("action", exclude=["action_listen"])
        second_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 1)
        latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=0)
        
        if second_last_user_utterance is not None:
            second_last_intent = second_last_user_utterance["parse_data"]["intent"]["name"]
            print("SECOND LAST user utterance: " + str(second_last_user_utterance))
            print("SECOND LAST USER INTENT: " +  str(second_last_intent) + "  TYPE: " + str(type(second_last_intent)))
        if latest_action is not None:
            print("LATEST EXECUTED ACTION:  " + str(latest_action["name"]) + ", TYPE: " + str(type(latest_action["name"])))
        if latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        second_latest_action = tracker.get_last_event_for("action", exclude=["action_listen"], skip=1)
        third_last_user_utterance = tracker.get_last_event_for("user", exclude=[], skip= 2)
        second_latest_slot_set = tracker.get_last_event_for("slot", exclude=['attack_name', 'attack_type', "problem", "target"], skip=1)
        
        if third_last_user_utterance is not None:
            third_last_intent = third_last_user_utterance["parse_data"]["intent"]["name"]
            print("THIRD LAST user utterance: " + str(third_last_user_utterance))
            print("THIRD LAST USER INTENT: " +  str(third_last_intent) + "  TYPE: " + str(type(third_last_intent)))
        if second_latest_action is not None:    
            print("LATEST EXECUTED ACTION:  " + str(second_latest_action["name"]) + ", TYPE: " + str(type(second_latest_action["name"])))
        if second_latest_slot_set is not None:
            print("LATEST SLOT SET: " + str(second_latest_slot_set["name"]) + ": " + str(latest_slot_set["value"]) + ", TYPE: " + str(type(latest_slot_set["value"])))

        print("#                        DEBUGGING END                       ")
        print("#############################################################")

    def __get_supported_attacks(self):
        ''' Returns a tuple including list of all supported attacks,
            as well as a nested dict specifying relations btw attacks. '''

        main_attacks = []
        subtypes = []
        specific_examples = []

        attack_relation_dict = {}

        with open('json/attack_information.json') as json_file:
            data_dict = json.load(json_file)

            # print("JSON File" + str(data_dict))
            for major_attack in data_dict:
                main_attacks.append(major_attack)
                
                # store main attack and its subtypes in attack_relation_dict
                # e.g {'ddos':{'children': ['volumetric', 'application layer', 'protocol based']}}
                # temp_dict = {}
                # children = data_dict[major_attack].keys()
                # temp_dict["children"] = children
                # attack_relation_dict["children"] = temp_dict
                 
            for attack in main_attacks:
                subtype_attacks = data_dict[attack]["subtypes"].keys()
                grandchildren = []
                for sub_attack in subtype_attacks:
                    subtypes.append(sub_attack)

                    temp_specific_attack_list = []
                    if "specific_attacks" in data_dict[attack]["subtypes"][sub_attack]:
                        spec_examples = data_dict[attack]["subtypes"][sub_attack]["specific_attacks"].keys()
                        for particular_example in spec_examples:
                            specific_examples.append(particular_example)
                            temp_specific_attack_list.append(particular_example)

                            # create relations of specific attack
                            temp_dict_particular_example = {}
                            temp_dict_particular_example["parent"] = sub_attack
                            temp_dict_particular_example["grandparent"] = attack
                            temp_dict_particular_example["attack_type"] = "specific_attack"

                            # add relations of specific attack
                            attack_relation_dict[particular_example] = temp_dict_particular_example
                    
                    # create relations of subattack 
                    temp_dict_sub_attack = {}
                    temp_dict_sub_attack["children"] = temp_specific_attack_list
                    grandchildren.extend(temp_specific_attack_list)
                    
                    temp_dict_sub_attack["parent"] = attack
                    temp_dict_sub_attack["attack_type"] = "subtype_attack"
                    
                    # add relations of subattack
                    attack_relation_dict[sub_attack] = temp_dict_sub_attack

                temp_dict_attack = {}
                temp_dict_attack["children"] = subtype_attacks
                temp_dict_attack["grandchildren"] = grandchildren
                temp_dict_attack["attack_type"] = "major_attack"

                attack_relation_dict[attack] = temp_dict_attack

        main_attacks.extend(subtypes)
        main_attacks.extend(specific_examples)

        # print("ALL AVAILABLE ATTACKS: " + str(main_attacks))
        # print("ATTACK RELATIONSHIPS: " + str(attack_relation_dict))

        # return a tuple
        return (main_attacks, attack_relation_dict)

    def __remove_invalid_attacks(self, attack_list, supported_attacks, dispatcher):
        invalid_attacks = []
        for attack in attack_list:
            if attack not in supported_attacks:
                invalid_attacks.append(attack)

        # remove attacks which are not covered in JSON file
        if len(invalid_attacks) != 0:
            for invalid_attack in invalid_attacks:
                if invalid_attack in attack_list:
                    attack_list.remove(invalid_attack)
        
                dispatcher.utter_message(text=("Sorry. I don't have any information about " + invalid_attack + " attack."))
        
        return attack_list



# How can I block an IP traffic using UFW?
class ActionSupport(Action):
     def name(self) -> Text:
         return "action_support"

     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         solution = str(tracker.get_slot('solution'))
         action = str(tracker.get_slot('action'))
         obj = str(tracker.get_slot('object'))

         with open('json/solutions.json') as json_file:
             data = json.load(json_file)
             if data[solution]:
                 if data[solution]['support'][action][obj]:
                     dispatcher.utter_message(text=("Yes. I can help you with that. You can use the command:"))
                     dispatcher.utter_message(text=(data[solution]['support'][action][obj]))
                 else:
                      dispatcher.utter_message(text=("Sorry. I don't have any information about that."))
             else:
                 dispatcher.utter_message(text=("Sorry. I don't have any information about that."))
         return []

# I have an iptables installed and want to protect my network against port scanning.
class ActionSolution(Action):

     def name(self) -> Text:
         return "action_solution"

     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         solution = str(tracker.get_slot('solution'))
         attack_name = str(tracker.get_slot('attack_name'))
         with open('json/solutions.json') as json_file:
             data = json.load(json_file)
             if data[solution]:
                 if data[solution]['protection_config'][attack_name]:
                     dispatcher.utter_message(text=("Yes. I can help you with that. You can use the command:"))
                     dispatcher.utter_message(text=(data[solution]['protection_config'][attack_name]))
                 else:
                     dispatcher.utter_message(text=("Sorry. I don't have any information about that."))
             else:
                 dispatcher.utter_message(text=("Sorry. I don't have any information about that."))
         return []

class ActionIdAttack(Action):
     def name(self) -> Text:
         return "action_idattack"

     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # global symptoms
        global current_symptoms
        global current_target
        print("these are the current symptoms: " + str(current_symptoms))
        symptoms = tracker.get_slot("problem")
        print("these are the new symptoms to be included: " + str(symptoms) + " type: " + str(type(symptoms)))
        target = tracker.get_slot("target")
        
        if symptoms == 'None' or target == 'None' or symptoms is None:
            if len(current_symptoms) == 0 or current_target == 'None' or current_target is None:
                dispatcher.utter_message(template='utter_attack_not_identified')
                return [SlotSet("identified_attack", None)]
        
        # if len(symptoms) != 0 and symptoms != 'None':
        #     for new_symptom in symptoms:
        #         if not new_symptom in current_symptoms and new_symptom != 'None':
        #             current_symptoms.append(new_symptom)
        #     print("these are the NEW current symptoms: " + str(current_symptoms))

        if len(symptoms) != 0 and symptoms != 'None':
            for new_symptom in symptoms:
                if new_symptom not in current_symptoms and new_symptom != 'None':
                    current_symptoms.append(new_symptom)
            print("these are the NEW current symptoms: " + str(current_symptoms))
        
        if target != 'None':
            current_target = target

        dispatcher.utter_message(text="I am now processing the submitted information..")
        tree = self.create_tree(target)
        if tree == False:
            dispatcher.utter_message(template='utter_attack_not_identified')
            return [SlotSet("identified_attack", None)]
                    
        ## Root and configurations
        current_branch = tree.is_branch("0")
        #symptoms = ["a lot of requests", "SYN packets"]
        #symptoms = ["overloaded","many connections","different IPs"]
        next_node = False
        is_leaf = False
        iterator = 0
        attack = False
        move = False
        # attack_identified = False
        #print(symptoms)
        print(current_symptoms)
        tree.show()
        ## Searching for attack type based on symptoms
        while(iterator<=len(current_symptoms)): # Search for the symptoms
            for i in current_branch: # For each entry in the tree level
                node = tree.get_node(i)
                if node.data in current_symptoms: # Verify if there is a symptom
                        next_node = i # If yes, move to the new symptom node
                        current_branch = tree.is_branch(next_node)
                        if(len(current_branch) == 1): # If it is a leaf, it is the attack type
                                is_leaf = True
                                attack = tree.get_node(current_branch[0])
                                break
            iterator = iterator + 1

        if (is_leaf):
                   dispatcher.utter_message(template='utter_attack_identified')
                   dispatcher.utter_message(text=(((attack.data))))
                   symptoms = []
                   current_symptoms = []
                   current_target = None
                   return [SlotSet("identified_attack", attack.data), SlotSet("problem", None), SlotSet("target", None)]
        else: # If the attack was not identified yet: Verify again if the next level has a leaf
                for i in current_branch:
                        if len(tree.is_branch(i)) == 0: # If it is a leaf, it is the attack type
                                is_leaf = True
                                attack = tree.get_node(i)
                                dispatcher.utter_message(template='utter_attack_identified')
                                dispatcher.utter_message(text=((str(attack.data))))
                                symptoms = []
                                current_symptoms = []
                                current_target = None
                                return [SlotSet("identified_attack", attack.data), SlotSet("problem", None), SlotSet("target", None)]
        # Otherwise
        if not(is_leaf):
            # dispatcher.utter_message(text=(("Attack not identified")))
            dispatcher.utter_message(template='utter_attack_not_identified')
            # attack_identified = False
            return [SlotSet("identified_attack", None)]

     def create_tree(self, target):
        tree = Tree()
        if target == "server":
            ## Creating the Tree
            # Target
            tree.create_node("server", '0', data="server") # root
            # Symptoms
            tree.create_node("a lot of requests", '01', data="a lot of requests", parent='0')
            tree.create_node("overloaded", '02', data="overloaded", parent='0')
            tree.create_node("unnatural traffic", '03', data="unnatural traffic", parent='0')
            # sub tree 1
            # a lot of requests
            tree.create_node("DDoS", '011', data="DDoS", parent='01')
            tree.create_node("many syn packets", '012', data="many syn packets", parent='01')
            # SYN packets
            tree.create_node("SYN flood", '0111', data="SYN flood", parent='012')
            # sub tree 2
            # lvl 1
            tree.create_node("DDoS", '021', data="DDoS", parent='02')
            tree.create_node("many connections", '022', data="many connections", parent='02')
            # lvl 2
            tree.create_node("different ips", '0221', data="different IPs", parent='022')
            # lvl 3
            tree.create_node("Botnet", '02211', data="Botnet", parent='0221')
            # sub tree 3
            # unnatural traffic
            # lvl 1
            tree.create_node("spikes at odd hours", '031', data="spikes at odd hours", parent='03')
            # lvl 2
            tree.create_node("DDoS", '0311', data='DDoS', parent='031')
        elif target == "computer":
            ## Creating the Tree
            # Target
            tree.create_node("computer", '0', data="computer") # root
            # Symptoms
            tree.create_node("acting weird", '01', data="acting weird", parent='0')
            tree.create_node("locked out", '02', data="locked out", parent='0')
            # sub tree 1
            # low computing performance
            tree.create_node("low computing performance", '011', data="low computing performance", parent='01')
            tree.create_node("a lot of requests", '012', data="a lot of requests", parent='01')
            # lvl 2
            # strange peep sounds
            tree.create_node("strange peep sounds", '0111', data="strange peep sounds", parent='011')
            # lvl 3
            # malware
            tree.create_node("malware", '01111', data="malware", parent='0111')
            # sub tree 2
            # lvl 1
            tree.create_node("demand ransom payment", '021', data="demand ransom payment", parent='02')
            # lvl 2
            tree.create_node("CryptoLocker ransomware", '0221', data="CryptoLocker ransomware", parent='021')
            # lvl 3
        else:
            return False

        return tree

class ActionSubmitSymptomForm(Action):

    def name(self):
        return "action_submit_symptom_form"
    
    def run(self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ):
        
        # global symptoms
        # print(symptoms)
        symptoms = []
        symptoms_1 = tracker.get_slot("symptoms_1")
        symptoms_2 = tracker.get_slot("symptoms_2")
        symptoms_target = tracker.get_slot("symptoms_target")
        identified_attack = tracker.get_slot("identified_attack")
        problem = tracker.get_slot("problem")
        # target = tracker.get_slot("target")
        
        intent = tracker.get_intent_of_latest_message()
        # dispatcher.utter_message(text="this is the current intent: " + str(intent))
        print("This is the current intent: " + str(intent))

        entities = tracker.latest_message.get("entities", [])
        # dispatcher.utter_message(text="these are the current entities: " + str(entities))
        print("These are the current entities: " + str(entities))


        # Even tough the slots of the forms are of type list, if only one entity gets
        # mapped to it, the slot is then automatically converted to a text type. If more than one
        # entities are mapped to that slot, they then will correctly be stored in a list.
        if symptoms_1 != "None":
            if type(symptoms_1) == str:
                symptoms.append(symptoms_1)
            else:
                for provided_symptom in symptoms_1:
                    symptoms.append(provided_symptom)
        

        if symptoms_2 != "None":
            if type(symptoms_2) == str:
                symptoms.append(symptoms_2)
            else:
                for provided_symptom in symptoms_2:
                    symptoms.append(provided_symptom)

        print("This is the value of the slot 'identified_attack': " + str(identified_attack))
        # dispatcher.utter_message(text="This is the value of the slot 'identified_attack': " + str(identified_attack))


        # attack_identified == False --> don't delete symptoms 
        # but give opportunity to add some more
        if problem != "None" and identified_attack == "None":
            for already_mentioned_symptom in problem:
                if not already_mentioned_symptom in symptoms:
                    symptoms.append(already_mentioned_symptom)


        if len(symptoms) != 0:
            print("Yay, it worked! You have submitted the following symptoms: " + str(symptoms))
            return [SlotSet("problem", symptoms), SlotSet("target", symptoms_target), SlotSet("symptoms_1", None), SlotSet("symptoms_2", None), SlotSet("symptoms_target", None)]
        else:
            print("You must give me more details or information about what is happening to be able to help you.")
            return [SlotSet("symptoms_1", None), SlotSet("symptoms_2", None), SlotSet("symptoms_target", None)]

class ValidateSymptomForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_symptom_form"

    def validate_symptoms_1(
        self,
        slot_value: List,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ):

        # print("VALIDATING SYMPTOMS_1 SLOT")
        if slot_value == 'None':
            dispatcher.utter_message(template="utter_explain_symptoms_1")
            dispatcher.utter_message(template="utter_stop_form")
            return {"symptoms_1": None}
        else:
            # print("SUCCESSFULL VALIDATION")
            return {"symptoms_1": slot_value}

    def validate_symptoms_2(
        self,
        slot_value: List,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ): 

        print("VALIDATING SYMPTOMS_2 SLOT")
        print("SUCCESSFULL VALIDATION")
        return {"symptoms_2": slot_value}

    def validate_symptoms_target(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ): 

        print("VALIDATING SYMPTOMS_TARGET SLOT")
        if slot_value == 'None':
            dispatcher.utter_message(template="utter_explain_symptoms_target")
            dispatcher.utter_message(template="utter_stop_form")
            return {"symptoms_target": None}
        else:
            return {"symptoms_target": slot_value}

class ActionSubmitMoreInfoForm(Action):
    def name(self):
        return "action_submit_more_info_form"
    
    def run(self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
        ):

        symptoms = []

        more_symptoms = tracker.get_slot("more_info")
        new_target = tracker.get_slot("new_target")
        print("more_info slot value: " + str(more_symptoms) + " type: " + str(type(more_symptoms)))

        # Even tough the slots of the forms are of type list, if only one entity gets
        # mapped to it, the slot is then automatically converted to a text type. If more than one
        # entities are mapped to that slot, they then will correctly be stored in a list.
        if type(more_symptoms) == str:
                if more_symptoms != 'None':
                    symptoms.append(more_symptoms)
        else:
            for provided_symptom in more_symptoms:
                if provided_symptom != 'None':
                    symptoms.append(provided_symptom)

        print("new info provided: " + str(symptoms))


        if new_target != "None":
            if len(symptoms)!= 0:
                return [SlotSet("problem", symptoms), SlotSet("target", new_target), SlotSet("more_info", None), SlotSet("new_target", None)]
            else:
                return [SlotSet("target", new_target), SlotSet("more_info", None), SlotSet("new_target", None)]
        return [SlotSet("problem", symptoms), SlotSet("more_info", None), SlotSet("new_target", None)]

class ValidateMoreInfoForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_more_info_form"

    def validate_more_info(
        self,
        slot_value: List,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ):
        print("VALIDATING MORE_INFO SLOT")
        print("slot_value: " + str(slot_value) + ", type: " + str(type(slot_value)))
        if slot_value == 'None':
            dispatcher.utter_message(template="utter_stop_form")
            dispatcher.utter_message(text="Otherwise provide the requested information.")
            print("Please do not back out:")
            return {"more_info": None}
        else:
            print("SUCCESSFULL VALIDATION")
            return {"more_info": slot_value}
       

    def validate_new_target(
        self,
        slot_value: List,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ): 
        print("VALIDATING NEW_TARGET SLOT")
        print("SUCCESSFULL VALIDATION")
        return {"new_target": slot_value}

class ActionResetSlotsAfterFormInterruption(Action):

    def name(self) -> Text:
        return "action_reset_slots_after_form_interruption"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        form_slots = ["symptoms_1", "symptoms_2", "symptoms_target", "more_info", "new_target"]

        for empty_slot in form_slots:
            if tracker.get_slot(empty_slot) is None:
                form_slots.remove(empty_slot)

        return [SlotSet(form_slot, None) for form_slot in form_slots]


# Should I invest in backups as a proactive approach to reduce possible Ransomware impacts?
# TODO: if no information, search on the database for averages
# TODO: Extend to support any attack
class ActionROSI(Action):

     def name(self) -> Text:
         return "action_ROSI"

     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         solution = str(tracker.get_slot('solution'))
         attack_name = str(tracker.get_slot('attack_name'))
         data = int(tracker.get_slot('CARDINAL'))
         revenue = 9000 # per day - TODO: from business profile
         downtime_average = 23 # days - TODO: according to the business sector average for a attack_name
         #data = 11 # 11 TB 
         price = 48 # 48 dollars per GB/monthly
         Tcost = 1500 # Ransomware rescue in USD
         RMC = downtime_average * revenue # in days - Loss Expectancy
         PMC = data*price # backup per month - Costs
         ROSI = ((RMC) - PMC)/PMC
         dispatcher.utter_message(text=(("The Return On Security Investment (ROSI) for your request is equal to" + str(ROSI))))
         if ROSI > 1:
             dispatcher.utter_message(text=(("Based on that, it is recommended you invest on" + solution + "for this case")))
         else:
             dispatcher.utter_message(text=(("Based on that, it is NOT recommended you invest on" + solution + "for this case")))

         print(ROSI)


         return []
