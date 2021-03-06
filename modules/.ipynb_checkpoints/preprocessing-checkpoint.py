import io
import os
import sys
import re
import json
import time
import regex
import signal
import string
import pickle
import numpy as np
import pandas as pd
from tqdm import trange

import pubchempy as pcp
from chemdataextractor import Document
from chemdataextractor.doc import Paragraph
from chemdataextractor.nlp.tokenize import ChemWordTokenizer

from mat2vec.processing.process import MaterialsTextProcessor


class SciTextProcessor():
    """
    Class that allows a variety of preprocessing functions to be applied to a set
    of scientific texts - either abstracts or full texts. Consists of functions for
        1. Cleaning - removing unwanted line breaks, tokens or words
        2. Normalizing - combining like words or phrases to single entities
            a. Chemical Entities
            b. Properties
    """
    def __init__(self, texts=None, type='abstract'):
        """
        Parameters:
            texts (list, required): list of texts to be preprocessed
            type (str): type of text to be processed (abstracts or full text)
        """
        self.type = type
        self.min_len = 5
        if texts is None:
            self.texts = []
        elif isinstance(texts, str):
            self.texts = [texts]
        else:
            self.texts = texts

        ### Element text and regex
        self.ELEMENTS = ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K",
                         "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
                         "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I",
                         "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
                         "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr",
                         "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf",
                         "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og", "Uue"]

        self.ELEMENT_NAMES = ["hydrogen", "helium", "lithium", "beryllium", "boron", "carbon", "nitrogen", "oxygen", "fluorine",
                              "neon", "sodium", "magnesium", "aluminium", "silicon", "phosphorus", "sulfur", "chlorine", "argon",
                              "potassium", "calcium", "scandium", "titanium", "vanadium", "chromium", "manganese", "iron",
                              "cobalt", "nickel", "copper", "zinc", "gallium", "germanium", "arsenic", "selenium", "bromine",
                              "krypton", "rubidium", "strontium", "yttrium", "zirconium", "niobium", "molybdenum", "technetium",
                              "ruthenium", "rhodium", "palladium", "silver", "cadmium", "indium", "tin", "antimony", "tellurium",
                              "iodine", "xenon", "cesium", "barium", "lanthanum", "cerium", "praseodymium", "neodymium",
                              "promethium", "samarium", "europium", "gadolinium", "terbium", "dysprosium", "holmium", "erbium",
                              "thulium", "ytterbium", "lutetium", "hafnium", "tantalum", "tungsten", "rhenium", "osmium",
                              "iridium", "platinum", "gold", "mercury", "thallium", "lead", "bismuth", "polonium", "astatine",
                              "radon", "francium", "radium", "actinium", "thorium", "protactinium", "uranium", "neptunium",
                              "plutonium", "americium", "curium", "berkelium", "californium", "einsteinium", "fermium",
                              "mendelevium", "nobelium", "lawrencium", "rutherfordium", "dubnium", "seaborgium", "bohrium",
                              "hassium", "meitnerium", "darmstadtium", "roentgenium", "copernicium", "nihonium", "flerovium",
                              "moscovium", "livermorium", "tennessine", "oganesson", "ununennium"]

        self.element_dict = {}
        for element, name in zip(self.ELEMENTS, self.ELEMENT_NAMES):
            self.element_dict[element] = name

        self.FORMULA_REGX = regex.compile(r"^("+r"|".join(self.ELEMENTS) +
                                          r"|[0-9])+$")
        self.VALENCE_REGX = regex.compile(r"^("+r"|".join(self.ELEMENTS) +
                                          r")(\(([IV|iv]|[Vv]?[Ii]{0,3})\))$")

        ### Numbers and units text and regex
        self.SPLIT_UNITS = ["K", "h", "V", "wt", "wt.", "MHz", "kHz", "GHz", "Hz", "days", "weeks",
                            "hours", "minutes", "seconds", "T", "MPa", "GPa", "at.", "mol.",
                            "at", "m", "N", "s-1", "vol.", "vol", "eV", "A", "atm", "bar",
                            "kOe", "Oe", "h.", "mWcm−2", "keV", "MeV", "meV", "day", "week", "hour",
                            "minute", "month", "months", "year", "cycles", "years", "fs", "ns",
                            "ps", "rpm", "g", "mg", "mAcm−2", "mA", "mK", "mT", "s-1", "dB",
                            "Ag-1", "mAg-1", "mAg−1", "mAg", "mAh", "mAhg−1", "m-2", "mJ", "kJ",
                            "m2g−1", "THz", "KHz", "kJmol−1", "Torr", "gL-1", "Vcm−1", "mVs−1",
                            "J", "GJ", "mTorr", "bar", "cm2", "mbar", "kbar", "mmol", "mol", "molL−1",
                            "MΩ", "Ω", "kΩ", "mΩ", "mgL−1", "moldm−3", "m2", "m3", "cm-1", "cm",
                            "Scm−1", "Acm−1", "eV−1cm−2", "cm-2", "sccm", "cm−2eV−1", "cm−3eV−1",
                            "kA", "s−1", "emu", "L", "cmHz1", "gmol−1", "kVcm−1", "MPam1",
                            "cm2V−1s−1", "Acm−2", "cm−2s−1", "MV", "ionscm−2", "Jcm−2", "ncm−2",
                            "Jcm−2", "Wcm−2", "GWcm−2", "Acm−2K−2", "gcm−3", "cm3g−1", "mgl−1",
                            "mgml−1", "mgcm−2", "mΩcm", "cm−2s−1", "cm−2", "ions", "moll−1",
                            "nmol", "psi", "mol·L−1", "Jkg−1K−1", "km", "Wm−2", "mass", "mmHg",
                            "mmmin−1", "GeV", "m−2", "m−2s−1", "Kmin−1", "gL−1", "ng", "hr", "w",
                            "mN", "kN", "Mrad", "rad", "arcsec", "Ag−1", "dpa", "cdm−2",
                            "cd", "mcd", "mHz", "m−3", "ppm", "phr", "mL", "ML", "mlmin−1", "MWm−2",
                            "Wm−1K−1", "Wm−1K−1", "kWh", "Wkg−1", "Jm−3", "m-3", "gl−1", "A−1",
                            "Ks−1", "mgdm−3", "mms−1", "ks", "appm", "ºC", "HV", "kDa", "Da", "kG",
                            "kGy", "MGy", "Gy", "mGy", "Gbps", "μB", "μL", "μF", "nF", "pF", "mF",
                            "A", "Å", "A˚", "μgL−1"]

        self.NUMBER_REGX = regex.compile(r"^[+-]?\d*\.?\d+\(?\d*\)?+$", regex.DOTALL)
        self.UNIT_REGX = regex.compile(r"^([+-]?\d*\.?\d+\(?\d*\)?+)([\p{script=Latin}|Ω|μ]+.*)", regex.DOTALL)
        self.PUNCT_REGX = list(string.punctuation) + ["\"", "“", "”", "≥", "≤", "×"]

        ### Clean texts - different logic for abstracts and full text
        if self.type == 'abstract':
            self.clean_texts = []
            self.dropped_idxs = []
            warned = False
            too_short = False
            for i, abstract in enumerate(self.texts):
                if abstract is None:
                    sys.stdout.write("\r\033[K"+"WARNING: TEXT LIST CONTAINS EMPTY ABSTRACTS. NOT ALL SAMPLES CAN BE CLEANED.")
                    warned = True
                    self.dropped_idxs[i]
                else:
                    abstract = self.clean_abstract(abstract)
                    if len(abstract) < self.min_len:
                        self.dropped_idxs.append(i)
                        too_short = True
                    else:
                        self.clean_texts.append(abstract)
            if too_short:
                sys.stdout.write("\r\033[K"+"WARNING: SOME ABSTRACTS WERE DROPPED DUE TO LENGTH. CHECK dropped_idxs FOR IDX NUMBERS.")
                print('\n')
            elif warned:
                print('\n')

        self.normalized_texts = []
        self.entity_counts = {}
        self.entities_per_text = {}
        self.entity_to_cid = {}
        self.entity_to_synonyms = {}
        self.tokenized_texts = {}
        self.entity_idxs = {}


    ########## CLEANING FUNCTIONS ###############

    def clean_abstract(self, abstract):
        """
        Takes an abstract and applies rules-based preprocessing to remove
        unwanted features from the raw Elsevier abstract download

        Parameters:
            abstract (str, required): The abstract which you want to clean

        Returns:
            cleaned_abstract (str): The cleaned abstract
        """
        abstract = abstract.split('\n')
        info = []
        for line in abstract:
            line = line.strip()
            if line != '':
                info.append(line)
        if len(info) == 2:
            clean_abstract = info[1]
        elif len(info) == 1:
            if info[0].split()[0].lower() == 'abstract':
                clean_abstract = ' '.join(info[0].split()[1:])
            elif info[0].split()[0].lower() == 'summary':
                clean_abstract = ' '.join(info[0].split()[1:])
            elif 'objective' in info[0].split()[0].lower():
                clean_abstract = ' '.join(info[0].split()[1:])
            else:
                clean_abstract = info[0]
        else:
            info_lower = [x.lower() for x in info]
            section_titles = ['introduction',
                              'purpose',
                              'background',
                              'scope and approach',
                              'objective',
                              'objectives',
                              'materials and methods',
                              'results',
                              'conclusion',
                              'conclusions',
                              'key findings',
                              'key findings and conclusions',
                              'methodology',
                              'methods',
                              'study design',
                              'clinical implications']
            sectioned = False
            for section_title in section_titles:
                if section_title in info_lower:
                    sectioned = True
            if sectioned:
                if info[0].lower() == 'abstract':
                    text = []
                    for entry in info[1:]:
                        if entry.lower() in section_titles:
                            pass
                        else:
                            text.append(entry)
                    clean_abstract = ' '.join(text)
                elif info[0].lower() == 'summary':
                    text = []
                    for entry in info[1::]:
                        if entry.lower() in section_titles:
                            pass
                        else:
                            text.append(entry)
                    clean_abstract = ' '.join(text)
                else:
                    text = []
                    for entry in info:
                        if entry.lower() in section_titles:
                            pass
                        else:
                            text.append(entry)
                    clean_abstract = ' '.join(text)
            else:
                if info[0].lower() == 'abstract' or info[0].lower() == 'absract' or info[0].lower() == 'abstact' or info[0].lower() == 'abstractt':
                    clean_abstract = ' '.join(info[1:])
                elif info[0].lower() == 'summary' or info[0].lower() == 'publisher summary' or info[0].lower() == '1. summary':
                    clean_abstract = ' '.join(info[1:])
                elif info[0] == 'This article has been retracted: please see Elsevier Policy on Article Withdrawal (https://www.elsevier.com/about/our-business/policies/article-withdrawal).':
                    clean_abstract = 'Retracted'
                else:
                    clean_abstract = ' '.join(info)

        clean_abstract = self.remove_symbols(clean_abstract)

        return clean_abstract

    def remove_symbols(self, abstract):
        """
        This function takes an abstract and removes the copywrite information
        followed by the Elsevier text and publication year and returns a clean
        abstract

        Parameters:
            abstract (str, required): The abstract which has unwanted copywrite text

        Returns:
            clean_abstract (str): The clean abstract
        """
        split = abstract.split()

        if '©' in split:
            if split[0] != '©':
                index = split.index('©')
                del split[index:]
                clean_abstract = ' '.join(split)
            elif split[0] == '©':
                if 'B.V.' in split:
                    new_idx = split.index('B.V.')
                    del split[0:new_idx+1]
                    clean_abstract = ' '.join(split)
                elif 'B.V..' in split:
                    new_idxs = split.index('B.V..')
                    del split[0:new_idxs+1]
                    clean_abstract = ' '.join(split)
                else:
                    del split[0:2]
                    clean_abstract = ' '.join(split)

        else:
            clean_abstract = abstract

        if '®' in clean_abstract:
            temp = list(clean_abstract)
            del temp[temp.index('®')]
            clean_abstract = "".join(temp)

        if clean_abstract.endswith(' Crown Copywrite'):
            clean_abstract.replace(' Crown Copywrite', '')

        clean_abstract = re.sub('<\w*>|<\/\w*>',' ', clean_abstract) #remove the unwanted HTML tags.
        return clean_abstract


    ############ NORMALIZATION FUNCTIONS ##############

    def normalize_chemical_entities(self, texts='default', remove_abbreviations=True,
                                    verbose=False, write_bold=False, search_attempts=10,
                                    save=False, save_freq=100, save_dir='preprocessor_files'):
        """
        Iterates through texts, extracts chemical entities and normalizes
        them

        Parameters:
            texts (list, required): List of texts to normalize
            remove_abbreviations (bool): If true then replace abbreviated
                                         entities with full name (only those
                                         extracted by chemdataextractor)
            verbose (bool): If true then prints text pre- and post-processing
            write_bold (bool): If true then prints chemical entities bolded to terminal
            save (bool): If true then saves texts, search history and run history
                         to preprocessor_files folder. WARNING: Running this function
                         twice without moving saved files will overwrite your previous
                         saves
        """
        ### Custom exception for catching server-side pubchem errors
        class TimeoutException(Exception):
            pass

        def timeout_handler(signum, frame):
            raise TimeoutException

        signal.signal(signal.SIGALRM, timeout_handler)

        self.timedout_entities = []

        if texts == 'default':
            texts = self.clean_texts

        ### Some entity names are ambiguous and must be hard coded
        self.entity_to_cid['CO'] = [281, 'carbon monoxide']
        self.entity_to_cid['Co'] = [104730, 'cobalt']
        self.entity_to_cid['NO'] = [145068, 'nitric oxide']
        self.entity_to_cid['No'] = [24822, 'nobelium']
        self.entity_to_cid['sugar'] = [None, None]
        self.entity_to_cid['chloro'] = [None, None]
        self.entity_to_cid['alcohol'] = [None, None]
        self.entity_to_synonyms['carbon monoxide'] = ['CO']
        self.entity_to_synonyms['cobalt'] = ['Co']
        self.entity_to_synonyms['nitric oxide'] = ['NO']
        self.entity_to_synonyms['nobelium'] = ['No']
        for k, v in self.entity_to_cid.items():
            if v[1] is None:
                self.entity_counts[k] = 1
            else:
                self.entity_counts[v[1]] = 1
        start_idx = len(self.normalized_texts)
        for i in trange(start_idx, len(texts)+start_idx):
            text_idx = i - start_idx
            text = texts[text_idx]
            ### Remove and normalize abbreviations
            if remove_abbreviations:
                text = self.remove_abbreviations(text)
            else:
                pass

            doc = Document(text)
            if verbose:
                print('---Text {}---'.format(text_idx+1))
                print(text+'\n')
            cems = doc.cems
            entity_list = []
            for cem in cems:
                ### Check if abbreviated valence state
                elem_valence = self.VALENCE_REGX.match(cem.text)
                if elem_valence:
                    elem = elem_valence.group(1)
                    valence = elem_valence.group(2)
                    elem = self.element_dict[elem]
                    cem.text = elem+valence

                ### Check if ambiguous formula
                if self.FORMULA_REGX.match(cem.text):
                    name = cem.text
                else:
                    name = cem.text.lower()

                ### Add entity name, start and stop indices to dictionary
                entity_list.append((name, cem.start, cem.end))

                ### Search entity in PubChem if not already done
                if name not in self.entity_to_cid.keys():
                    c = self.search_pubchem(name, search_attempts, TimeoutException)
                    signal.alarm(0)
                    if len(c) == 0:
                        self.entity_to_cid[name] = [None, None]
                        self.entity_counts[name] = 1
                    else:
                        c = c[0]
                        cid = c.cid
                        iupac_name = c.iupac_name
                        if iupac_name is not None:
                            self.entity_to_cid[name] = [cid, iupac_name]
                            if iupac_name not in self.entity_to_synonyms.keys():
                                self.entity_to_synonyms[iupac_name] = [name]
                            else:
                                self.entity_to_synonyms[iupac_name].append(name)
                            self.entity_counts[self.entity_to_cid[name][1]] = 1
                        else:
                            self.entity_to_cid[name] = [cid, None]
                            self.entity_counts[name] = 1
                else:
                    if self.entity_to_cid[name][1] is None:
                        self.entity_counts[name] += 1
                    else:
                        self.entity_counts[self.entity_to_cid[name][1]] += 1

            ### Sort named entities by location in text and replace with synonym
            entity_list.sort(key=lambda x:x[1])
            index_change = 0
            self.entities_per_text[i] = []
            for entity in entity_list:
                name, start, stop = entity
                if self.entity_to_cid[name][1] is not None:
                    replacement_name = self.entity_to_cid[name][1]
                else:
                    replacement_name = name
                if write_bold:
                    replacement_delta = len(replacement_name) - (stop - start) + 8
                    text = text[:start+index_change] + '\033[1m' + replacement_name + '\033[0m' + text[stop+index_change:]
                else:
                    replacement_delta = len(replacement_name) - (stop - start)
                    text = text[:start+index_change] + replacement_name + text[stop+index_change:]
                index_change += replacement_delta
                self.entities_per_text[i].append((replacement_name, start+index_change-replacement_delta, stop+index_change, name))
            if verbose:
                print(text)
                print('\n')

            self.normalized_texts.append(text)

            ### Save every n abstracts
            if (i+1) % save_freq == 0 or i == len(texts) + start_idx - 1:
                if save:
                    os.makedirs(save_dir, exist_ok=True)
                    with open('{}/normalized_texts.txt'.format(save_dir), 'w') as f:
                        for text in self.normalized_texts:
                            f.write(text+'\n')

                    for iupac_name, synonyms in self.entity_to_synonyms.items():
                        self.entity_to_synonyms[iupac_name] = list(set(synonyms))
                    search_history = {'entity_to_cid': self.entity_to_cid,
                                      'entity_to_synonyms': self.entity_to_synonyms}

                    with io.open('{}/search_history.json'.format(save_dir), 'w', encoding='utf8') as f: # map of entity names to CID/iupac names for quick recall
                        out_ = json.dumps(search_history,                                              # map of CIDs to all unique synonyms
                                          indent=4, sort_keys=False,
                                          separators=(',', ': '), ensure_ascii=False)
                        f.write(str(out_))

                    preprocess_history = {'entities_per_text': self.entities_per_text,
                                          'entity_counts': self.entity_counts}

                    with io.open('{}/preprocess_history.json'.format(save_dir), 'w', encoding='utf8') as f: # list of entities in each text with span
                        out_ = json.dumps(preprocess_history,                                              # dictionary of unique entities and their number of occurrences
                                          indent=4, sort_keys=False,
                                          separators=(',', ': '), ensure_ascii=False)
                        f.write(str(out_))

    def search_pubchem(self, name, attempts, TimeoutException):
        """
        This function searches pubchem api for named entity and catches exceptions
        if the search is taking too long

        Parameters:
            name (str, required): name of entity to search in pubchem
            attempts (int, required): number of search attempts to try before exiting
                                      the function (only relevant when search takes
                                      longer than 10 seconds)
            TimeoutException (exception, required): custom exception for catching
                                                    timeout errors
        Returns:
            c (list): list of pubchem compound objects
        """
        for i in range(attempts):
            try:
                signal.alarm(10)
                c = pcp.get_compounds(name, 'name')
                return c
            except TimeoutException:
                continue
        c = []
        print("WARNING: ENTITY '{}' TIMED OUT {} TIMES".format(name, attempts))
        self.timedout_entities.append(name)
        return c

    def remove_abbreviations(self, text):
        """
        A text is sent to chemdataextractor which finds all chemical
        abbreviations. The first instance of the abbreviation is removed based on
        some heuristic rules (intended to remove its initial definition) and the
        rest are replaced with the full name

        Parameters:
            text (str, required): the text from which abbreviations should be removed
        Returns:
            text (str): processed text with no abbreviations extracted
        """
        escape_chars = ['+']
        doc = Document(text)
        abbvs = doc.abbreviation_definitions
        cems = doc.cems
        if len(abbvs) > 0:
            abbv_dict = {}
            for abbv in abbvs:
                cem_starts = []
                cem_ends = []
                if abbv[-1] is not None:
                    abbv_name = abbv[0][0]
                    escape_abbv = ''
                    for char in abbv_name:
                        if char in escape_chars:
                            escape_abbv += r'\{}'.format(char)
                        else:
                            escape_abbv += char
                    abbv_name = escape_abbv
                    abbv_dict[abbv_name] = [' '.join(abbv[1])]
                    for cem in cems:
                        if cem.text == abbv_name:
                            cem_starts.append(cem.start)
                            cem_ends.append(cem.end)
                    if len(cem_starts) > 0:
                        low_idx = cem_starts[np.argmin(cem_starts)]
                    else:
                        low_idx = 0
                    abbv_dict[abbv_name].append(low_idx)
            abbv_dict = {k: v for k, v in sorted(abbv_dict.items(), key=lambda item: item[1][1])}
            index_change = 0
            for abbv in abbv_dict.keys():
                non_abbv = abbv_dict[abbv][0]
                if abbv_dict[abbv][1] != 0:
                    replacement_delta = len(non_abbv) - len(abbv)
                    cem_starts = []
                    cem_ends = []
                    for cem in cems:
                        if cem.text == abbv:
                            cem_starts.append(cem.start)
                            cem_ends.append(cem.end)
                    if len(cem_starts) == 1:
                        if text[cem_starts[0]+index_change-1]+text[cem_ends[0]+index_change] == '()':
                            text = text[:cem_starts[0]-2+index_change] + text[cem_ends[0]+1+index_change:]
                            index_change += cem_starts[0] - cem_ends[0] - 3
                        else:
                            pass
                    else:
                        low_idx = np.argmin(cem_starts)
                        cem_start_low = cem_starts[low_idx]
                        cem_end_low = cem_ends[low_idx]
                        if text[cem_start_low+index_change-1]+text[cem_end_low+index_change] == '()':
                            text = text[:cem_start_low-2+index_change] + text[cem_end_low+1+index_change:]
                            index_change += cem_start_low - cem_end_low - 3
                        else:
                            pass
                    text = re.sub(r'([\s]){}([.,;\s]|$)'.format(abbv), r' {}\2'.format(non_abbv), text)
                else:
                    pass
        return text

    def normalize_phrases(self, phrases='default'):
        if phrases == 'default':
            phrases = self.phrases
        pass

    def generate_phrases(self, texts='default', save=False):
        if texts == 'default':
            texts = self.clean_texts
        elif texts == 'chem_norm':
            texts = self.normalized_texts

        # CODE TO GENERATE LIST OF PHRASES
        self.phrases = list_of_phrases
        if save:
            pass
            # CODE TO SAVE PHRASES IN PREPROCESSING FILE

    def normalize(self):
        self.normalize_chemical_entities()
        self.normalize_phrases()


    ########### TOKENIZING FUNCTIONS #############
    """
    Much of the tokenizing functionality has been adapted from the tokenization workflow
    in "Unsupervised word embeddings capture latent knowledge from materials science
    literature" (10.1038/s41586-019-1335-8)
    """

    def tokenize(self, texts='default', entities='default', use_entities=True,
                 keep_sentences=True, exclude_punct=False, save=False):
        """
        Takes the set of normalized texts and tokenizes them

        Parameters:
            texts (list): List of texts to tokenize. If `default` then
                          self.normalized_texts will be used
            entities (dict): Dictionary of entity names and index positions. If
                             `default` then self.entities_per_text will be used
            use_entities (bool): If true then entity dict will be used to tokenize
                                 multi-word phrases and chemical entities. Otherwise
                                 all words in text list will be tokenized with the
                                 same algorithm and some entities may be split
            keep_sentences (bool): If true then abstract will be split into list of
                                   lists where each nested list is a single sentence.
                                   Otherwise abstract will be split into a single list
                                   of tokens
            exclude_punct (bool): If true then common punctuation marks will be left out
                                  of token list. Otherwise all punctuation will remain
        """
        if texts == 'default':
            texts = self.normalized_texts
        if entities == 'default':
            entities = self.entities_per_text
        if use_entities:
            assert len(texts) == len(entities), "ERROR: SIZE OF ENTITY AND TEXT LISTS DO NOT MATCH. YOU CAN EITHER RUN A NORMALIZATION FUNCTION ON UNPROCESSED TEXT OR LOAD FILES OF MATCHING SIZE"

        ### Instantiate Mat2Vec MaterialsTextProcessor
        MTP = MaterialsTextProcessor()

        ### Iterate through all abstracts and corresponding entities if applicable
        for i in trange(len(texts)):
            text = texts[i]
            entity_spans = []
            if use_entities:
                entry = entities[i]
                for entity in entry:
                    name = entity[0]
                    start = entity[1]
                    stop = entity[2]
                    entity_spans.append((start, stop))
                    new_name = name.replace(' ', '_')
                    text = text[:start] + new_name + text[stop:]

            if keep_sentences == False:
                ### Split text into entities vs. non-entities
                token_list = self.extract_entity_tokens(text, entity_spans)

                ### Tokenize non-entities and combine with entities
                tokens, self.entity_idxs[i] = self.process_token_list(token_list)

                ### Use Mat2Vec MaterialsTextProcessor for casing, number normalization, puncutation, etc.
                tokens, _ = MTP.process(tokens,
                                        exclude_punct=exclude_punct,
                                        normalize_materials=False,
                                        split_oxidation=False)
            else:
                ### Split text into sentences
                tokens = []
                self.entity_idxs[i] = []
                para = Paragraph(text)
                prior_split = 0
                for j, sentence in enumerate(para.sentences):
                    split = sentence.end
                    sentence = sentence.text
                    sentence_entities = []
                    for span in entity_spans:
                        if span[1] < split and span[0] >= prior_split:
                            new_span = (span[0] - split, span[1] - split)
                            sentence_entities.append(new_span)
                    prior_split = split

                    ### Make a token_list for each sentence
                    token_list = self.extract_entity_tokens(sentence, sentence_entities)

                    ### Tokenize non-entities and combine with entities
                    sentence_tokens, sentence_entity_idxs = self.process_token_list(token_list)
                    self.entity_idxs[i].append(sentence_entity_idxs)

                    ### Mat2Vec Processing
                    sentence_tokens, _ = MTP.process(sentence_tokens,
                                                     exclude_punct=exclude_punct,
                                                     normalize_materials=False,
                                                     split_oxidation=False)
                    tokens.append(sentence_tokens)
            self.tokenized_texts[i] = tokens

        if save:
            os.makedirs('preprocessor_files', exist_ok=True)

            with io.open('preprocessor_files/tokenized_texts.json', 'w', encoding='utf8') as f:
                out_ = json.dumps(self.tokenized_texts,
                                  indent=4, sort_keys=False,
                                  separators=(',', ': '), ensure_ascii=False)
                f.write(str(out_))

            with io.open('preprocessor_files/tokenized_entity_idxs.json', 'w', encoding='utf8') as f:
                out_ = json.dumps(self.entity_idxs,
                                  indent=4, sort_keys=False,
                                  separators=(',', ': '), ensure_ascii=False)
                f.write(str(out_))

    def extract_entity_tokens(self, text, entity_spans):
        """
        Takes a string of text and a list of entity idxs and extracts entities
        locations so remaining text can be automatically tokenized by ChemWordTokenizer

        Parameters:
            text (str, required): A string of text containing known entities that
                                  are not identifiable through pre-existing packages
            entity_spans (list, required): A list of start and stop idxs for each entity
                                           indicating where they appear in the text
        Returns:
            token_list (list): A list containing portions of unparsed text as well as
                              entities (differentiated by their placement in nested
                              lists)
        """
        token_list = []
        prev_start = 0
        if len(entity_spans) > 0:
            for j, span in enumerate(entity_spans):
                start = span[0]
                stop = span[1]
                text_add = text[prev_start:start]
                if text_add != '':
                    token_list.append(text_add)
                token_list.append([text[start:stop]])
                if j == len(entity_spans) - 1:
                    token_list.append(text[stop:])
                prev_start = stop
        else:
            token_list = [text]
        return token_list

    def process_token_list(self, token_list):
        """
        Takes the token_list returned from extract_entity_tokens(), processes
        the non-entity portions and combines all tokens into a single list. It
        also stores the entity names and list idxs in a dictionary

        Parameters:
            token_list (list, required): list of texts to be tokenized and already
                                         tokenized entities
        Returns:
            tokens (list): ordered list of tokens for the whole text
            entity_idxs (list): list of items and their token idx for each list
        """
        tokens = []
        entity_idxs = []
        CWT = ChemWordTokenizer()
        for j, item in enumerate(token_list):
            if isinstance(item, str):
                item_tokens = CWT.tokenize(item)
                ### Split numbers from common units
                split_tokens = []
                for token in item_tokens:
                    split_tokens += self.split_token(token)
                tokens += split_tokens
            else:
                tokens += item
                item_idx = len(tokens) - 1
                entity_idxs.append([item[0], item_idx])
        return tokens, entity_idxs

    def split_token(self, token):
        """
        Processes a single token, in case it needs to be split up (this function
        is adapted from https://github.com/materialsintelligence/mat2vec)

        Parameters:
            token (str, required): The token to be processed.
        Returns:
            token: The processed token.
        """
        nr_unit = self.UNIT_REGX.match(token)
        if nr_unit is not None and nr_unit.group(2) in self.SPLIT_UNITS:
            # Splitting the unit from number, e.g. "5V" -> ["5", "V"].
            return [nr_unit.group(1), nr_unit.group(2)]
        else:
            return [token]


    ########### LOADING FUNCTIONS ###############

    def load_search_history(self, path):
        """
        Loads a series of PubChem searches so those terms will not be searched
        again in subsequent runs

        Parameters:
            path (str, required): Path to json file containing search history
                                  dictionaries
        """
        with open(path) as f:
            search_history = json.load(f)
        self.entity_to_cid = search_history['entity_to_cid']
        self.entity_to_synonyms = search_history['entity_to_synonyms']

    def load_preprocess_history(self, path):
        """
        Loads dictionaries of entity names and counts

        Parameters:
            path (str, required): Path to json file containing preprocessing history
        """
        with open(path) as f:
            preprocess_history = json.load(f)
        entities_per_text = preprocess_history['entities_per_text']
        self.entity_counts = preprocess_history['entity_counts']
        for k, v in entities_per_text.items():
            self.entities_per_text[int(k)] = v

    def load_normalized_texts(self, path):
        """
        Loads a list of normalized texts

        Parameters:
            path (str, required): Path to numpy file containing normalized texts
        """
        with open(path, 'r') as f:
            for line in f:
                line = line.split('\n')[0]
                self.normalized_texts.append(line)

    def load_tokenized_texts(self, path):
        """
        Loads a dictionary of tokenized texts

        Parameters:
            path (str, required): Path to json file containing tokenized texts
        """
        with open(path) as f:
            tokenized_texts = json.load(f)
        for k, v in tokenized_texts.items():
            self.tokenized_texts[int(k)] = v

    def load_tokenized_entity_idxs(self, path):
        """
        Loads a dictionary containing the index locations of entity tokens in each
        text

        Parameters:
            path (str, required): Path to json file containing entity idxs
        """
        with open(path) as f:
            entity_idxs = json.load(f)
            for k, v in entity_idxs.items():
                self.entity_idxs[int(k)] = v

    def load_phrases(self, path):
        """
        Code to load phrase file
        """
        pass

    def load_normalizer(self, dir):
        """
        Loads all manually created preprocessor save files prior to tokenization.
        Files must have the same name as when written by the SciTextProcessor object

        Parameters:
            dir (str, required): Path to folder containing save files
        """
        fns = os.listdir(dir)
        for fn in fns:
            path = os.path.join(dir, fn)
            if fn == 'normalized_texts.txt':
                self.load_normalized_texts(path)
            elif fn == 'search_history.json':
                self.load_search_history(path)
            elif fn == 'preprocess_history.json':
                self.load_preprocess_history(path)

    def load_preprocessor(self, dir):
        """
        Loads all manually created preprocessor save files. Files must have the
        same name as when written by the SciTextProcessor object

        Parameters:
            dir (str, required): Path to folder containing save files
        """
        fns = os.listdir(dir)
        for fn in fns:
            path = os.path.join(dir, fn)
            if fn == 'normalized_texts.txt':
                self.load_normalized_texts(path)
            elif fn == 'search_history.json':
                self.load_search_history(path)
            elif fn == 'preprocess_history.json':
                self.load_preprocess_history(path)
            elif fn == 'tokenized_texts.json':
                self.load_tokenized_texts(path)
            elif fn == 'tokenized_entity_idxs.json':
                self.load_tokenized_entity_idxs(path)
