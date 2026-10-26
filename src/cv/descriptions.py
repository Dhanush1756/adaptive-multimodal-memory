"""Optional cached SmolVLM descriptions, never identity proof or verified facts."""
from pathlib import Path


class LocalDescriptions:
    def __init__(self, config):
        self.config=config
        self.identity=None
        self.model=self.processor=None
        self.notice='Descriptions disabled; no vision-language inference.'
        if not config.get('description_model_path'):return
        path=Path(config['description_model_path'])
        if not path.is_dir():
            self.notice='Local description assets missing; unknown descriptions.';return
        try:
            import torch
            from transformers import AutoProcessor, SmolVLMForConditionalGeneration
            self.processor=AutoProcessor.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
            self.model=SmolVLMForConditionalGeneration.from_pretrained(str(path),local_files_only=True,
                trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float32).eval()
            import hashlib
            digest=hashlib.sha256()
            for file in sorted(path.rglob('*.safetensors')):
                digest.update(file.name.encode())
                with file.open('rb') as stream:
                    while chunk:=stream.read(1024*1024):digest.update(chunk)
            self.identity='SmolVLM-compatible:'+digest.hexdigest()
            self.notice='Local assets loaded; description quality unverified.'
        except Exception:
            self.model=self.processor=None
            self.notice='Description runtime unavailable/incompatible; unknown descriptions.'

    def describe(self,image):
        if self.model is None:return {'text':None,'status':'unavailable','verified':False}
        try:
            import torch
            prompt=self.processor.apply_chat_template([{'role':'user','content':[
                {'type':'image'}, {'type':'text','text':'Describe only visible objects and their spatial arrangement. Do not infer identity, ownership, emotions, ethnicity, age, health, religion or other sensitive personal attributes.'}]}],add_generation_prompt=True)
            inputs=self.processor(text=prompt,images=[image],return_tensors='pt')
            with torch.inference_mode():result=self.model.generate(**inputs,max_new_tokens=64,do_sample=False)
            text=self.processor.batch_decode(result[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
            # Restrictive output gate; not a complete sensitive-attribute detector.
            import re
            if re.search(r'\b(?:ethnic|race|religion|Muslim|Christian|Hindu|pregnant|disabled|disease|years old|male|female|emotion|happy|sad)\b',text,re.I):
                return {'text':None,'status':'sensitive_or_unsupported_description','verified':False}
            return {'text':text[:1000],'status':'unverified_model_description','verified':False,
                    'model':self.identity,'not_used_for_memory_acceptance':True}
        except Exception:return {'text':None,'status':'inference_failed','verified':False}
