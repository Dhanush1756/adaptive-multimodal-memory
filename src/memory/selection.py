"""Deterministic explicit-claim extraction and independent usefulness selection.

No model, probabilistic calibration, arbitrary coreference or semantic extraction
is claimed. Unknown language stays in the transcript, not in long-term memory.
"""
from dataclasses import dataclass
from datetime import timezone
import re

from .schema import Claim
from ..nlp.relation_extraction import extract_claims, COLOR_WORDS
from .conflict import normalize_value
from ..nlp.temporal_extraction import resolve_event_time
from ..utils import parse_ts, iso

EXTRACTOR_VERSION = 'general-explicit-rules-v2'


def is_query_text(text):
    return '?' in text or bool(re.match(
        r'\s*(what|which|who|when|where|how|tell|show|do|did|does|is|was|are|were|can|could|will|would|remember)\b',
        text,re.I))


def extract_candidates(text, reference):
    claims = []
    for sentence in re.split(r';|\n+|(?<=[.!?])\s+', text):
        sentence = sentence.strip()
        sentence = re.sub(r'^(?:correction|actually|update)\s*[:,]?\s*', '', sentence, flags=re.I)
        sentence = re.sub(r'^(?:please\s+)?remember(?:\s+that)?\s+', '', sentence, flags=re.I)
        if not sentence or is_query_text(sentence) or re.search(
                r"\b(maybe|perhaps|might|could|guess|assume|suppose|if)\b", sentence, re.I):
            continue
        sentence = sentence.rstrip('.!').strip()
        # Retain explicit negative constraints verbatim, never as positive facts.
        negative = re.fullmatch(r"I ((?:do not|don't|never) (?:use|eat|like) .+)",sentence,re.I)
        if negative:
            claims.append(Claim('user','constraint',negative[1].lower(),entity_ref='self',
                source_text=sentence,confidence=.9,resolved_time=iso(parse_ts(reference))))
            continue
        if re.search(r"\b(not|never)\b|n't",sentence,re.I):
            continue
        claim = None
        # Explicit category + reference + arbitrary attribute; values remain text.
        named = re.fullmatch(r"(?:my|our|the) ([\w-]+) named ([\w-]+)(?:'s)? ([\w -]{1,50}?) (?:is|are|uses) (.+)", sentence, re.I)
        plain = re.fullmatch(r"(?:my|our) ([\w-]+)(?:'s)? ([\w -]{1,50}?) (?:is|are) (.+)", sentence, re.I)
        pref = re.fullmatch(r'I (?:now )?(?:prefer|like|enjoy) (.+)', sentence, re.I)
        residence = re.fullmatch(r'I (?:now )?live in (.+)',sentence,re.I)
        due = re.fullmatch(r'(?:my |our )?project (?:named )?([\w-]+) is due (?:on )?(\d{4}-\d{2}-\d{2})',sentence,re.I)
        obligation = re.fullmatch(r'(?:my |our )?project (?:named )?([\w-]+) (?:must|needs to) (.+)',sentence,re.I)
        reverse_relationship = re.fullmatch(r'My (supervisor|manager|mentor|advisor|colleague|partner) is ([\w -]+)',sentence,re.I)
        relationship = re.fullmatch(r'([\w-]+) is my ([\w -]{1,40})', sentence, re.I)
        requirement = re.fullmatch(r'(?:my|our) (?:new |previous )?requirement is (.+)', sentence, re.I)
        plan = re.fullmatch(r'(?:we|I) (?:decided|plan) to train (.+)', sentence, re.I)
        named_colour = re.fullmatch(r"(?:my|our) ([\w-]+) named ([\w-]+) is ("+'|'.join(COLOR_WORDS)+r")", sentence, re.I)
        if named:
            entity, ref, attr, value = named.groups()
            claim = Claim(entity.lower(), attr.lower().strip(), value.lower().strip(), entity_ref=ref.lower())
        elif named_colour:
            claim = Claim(named_colour[1].lower(), 'color', normalize_value(named_colour[3]), entity_ref=named_colour[2].lower())
        elif requirement or plan:
            match = requirement or plan
            claim = Claim('project', 'requirement' if requirement else 'model', match[1].lower(), entity_ref='default project')
        elif residence:
            claim = Claim('user','location',residence[1].lower(),entity_ref='self')
        elif due:
            try:
                parse_ts(due[2])
            except ValueError:
                continue
            claim = Claim('project','deadline',due[2],entity_ref=due[1].lower())
        elif obligation:
            claim = Claim('project','requirement',obligation[2].lower(),entity_ref=obligation[1].lower())
        elif reverse_relationship:
            claim = Claim('user',reverse_relationship[1].lower(),reverse_relationship[2].lower(),entity_ref='self')
        elif pref:
            claim = Claim('user', 'preference', pref[1].lower(), entity_ref='self')
        elif relationship:
            claim = Claim('user', relationship[2].lower(), relationship[1].lower(), entity_ref='self')
        elif plain:
            entity, attr, value = plain.groups()
            # "my first car is red" belongs to the ordinal colour extractor.
            if entity.lower() not in {'first','second','third','new','old'}:
                claim = Claim(entity.lower(), attr.lower().strip(), value.lower().strip())
                if entity.lower() == 'project':
                    claim.entity_ref = None
        if claim:
            claim.source_text, claim.confidence = sentence, .9
            event = resolve_event_time(sentence, reference=reference)
            # A date-valued attribute is not the date the user observed the claim.
            date_attribute = any(x in claim.attribute for x in ('deadline','date','birthday'))
            if event and event.resolved and not date_attribute:
                claim.resolved_time = iso(event.resolved)
            else:
                claim.resolved_time = iso(parse_ts(reference))
            claims.append(claim)
        else:
            # No implicit cross-conversation entity fallback during extraction.
            extracted = extract_claims(sentence, reference)
            for item in extracted:
                if not item.resolved_time:
                    item.resolved_time = iso(parse_ts(reference))
            claims.extend(extracted)
            if not extracted:
                colour = re.fullmatch(r"(?:my|our) ([\w-]+)(?: named ([\w-]+))? is ("+'|'.join(COLOR_WORDS)+r")", sentence, re.I)
                if colour:
                    claims.append(Claim(colour[1].lower(), 'color', normalize_value(colour[3]),
                        entity_ref=colour[2].lower() if colour[2] else None, source_text=sentence,
                        confidence=.9, resolved_time=iso(parse_ts(reference))))
    return claims


@dataclass
class Selection:
    outcome: str
    reason: str
    usefulness: float
    confidence: float


class SelectionPolicy:
    version = 'explicit-usefulness-v1'

    def __init__(self, config=None):
        cfg = config or {}
        self.minimum = float(cfg.get('minimum_usefulness', .65))
        self.minimum_confidence = float(cfg.get('minimum_confidence', .8))
        self.default_usefulness = float(cfg.get('default_usefulness', .7))
        self.weights = {'preference': .9, 'requirement': .95, 'deadline': .95,
                        'model': .85, 'goal': .9, 'plan': .85, 'commitment': .9,
                        'status': .75, 'color': .7}
        self.weights.update(cfg.get('attribute_usefulness', {}))
        self.transient = set(cfg.get('transient_attributes', ['mood','snack','weather']))
        for number in (self.minimum, self.minimum_confidence, self.default_usefulness, *self.weights.values()):
            if not 0 <= number <= 1:
                raise ValueError('Memory-selection scores must be between zero and one.')

    def evaluate(self, claim, existing, *, explicit=False):
        usefulness = float(self.weights.get(claim.attribute, self.default_usefulness))
        if claim.attribute in self.transient:
            usefulness = .2
        if explicit:
            usefulness = 1.0
        def result(outcome, reason):
            return Selection(outcome, reason, usefulness, claim.confidence)
        if re.search(r'password|secret|token|api.key|credit.card', claim.attribute, re.I):
            return result('reject', 'Sensitive attributes are not promoted automatically.')
        if claim.confidence < self.minimum_confidence:
            return result('clarify', 'Extraction confidence is below the configured gate.')
        identities = {(r.entity_id, r.entity_ref) for r in existing if r.entity == claim.entity}
        if not claim.entity_ref and len(identities) > 1:
            return result('clarify', 'More than one entity matches; supply an explicit identity.')
        relevant = [r for r in existing if r.entity == claim.entity and r.attribute == claim.attribute
                    and (not claim.entity_ref or r.entity_ref == claim.entity_ref)
                    and r.status.value not in {'CONTRADICTORY','RESOLVED'}]
        relevant.sort(key=lambda r: parse_ts(r.timestamp))
        event_time = parse_ts(claim.resolved_time)
        prior = [r for r in relevant if parse_ts(r.timestamp) <= event_time]
        # Do not suppress late observations that extend a known state's validity.
        if prior and prior[-1].value == claim.value.strip().lower():
            return result('duplicate', 'Equivalent state already valid at this event time; transcript retained.')
        if usefulness < self.minimum:
            return result('history_only', 'Future-usefulness estimate is below the configured threshold.')
        return result('promote', 'Explicit attributable fact passes usefulness, confidence and identity gates.')
