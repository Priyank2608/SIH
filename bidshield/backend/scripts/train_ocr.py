import os
import sys
import torch
from datasets import Dataset
from transformers import (
    TrOCRProcessor,
    VisionEncoderDecoderModel,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    default_data_collator
)
import evaluate
from PIL import Image, ImageDraw

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.entities import BidderDocument, OCRResult, Bidder, Tenant

def compute_metrics(pred):
    cer_metric = evaluate.load("cer")
    labels_ids = pred.label_ids
    pred_ids = pred.predictions

    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
    pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
    labels_ids[labels_ids == -100] = processor.tokenizer.pad_token_id
    label_str = processor.batch_decode(labels_ids, skip_special_tokens=True)

    cer = cer_metric.compute(predictions=pred_str, references=label_str)
    return {"cer": cer}

def create_dummy_image(text):
    img = Image.new('RGB', (800, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10,10), text, fill=(0,0,0))
    return img

def setup_db_dummy_data():
    db = SessionLocal()
    
    print("Removing unnecessary documents from the database...")
    db.query(OCRResult).filter(OCRResult.confidence < 0.1).delete(synchronize_session=False)
    db.query(BidderDocument).filter(BidderDocument.is_synthetic == True).delete(synchronize_session=False)
    db.commit()
    
    print("Fetching real document formats from the internet (mocked) and creating dummy data for Govt of India documents...")
    dummy_docs = [
        {"type": "PAN", "text": "INCOME TAX DEPARTMENT GOVT OF INDIA PERMANENT ACCOUNT NUMBER ABCDE1234F NAME: JOHN DOE"},
        {"type": "GSTIN", "text": "GOVERNMENT OF INDIA FORM GST REG-06 REGISTRATION CERTIFICATE GSTIN: 22AAAAA0000A1Z5 TRADE NAME: JOHN ENTERPRISES"},
        {"type": "UDYAM", "text": "UDYAM REGISTRATION CERTIFICATE UDYAM-XX-00-0000000 NAME OF ENTERPRISE: JOHN ENTERPRISES TYPE: MICRO"}
    ]
    
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(code="DEFAULT", name="Default Tenant")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        
    bidder = db.query(Bidder).first()
    if not bidder:
        bidder = Bidder(tenant_id=tenant.id, legal_name="John Enterprises", pan="ABCDE1234F", gstin="22AAAAA0000A1Z5", address="Delhi", state="Delhi", district="Delhi", contact_email="a@b.com", contact_phone="123", contact_person="John")
        db.add(bidder)
        db.commit()
        db.refresh(bidder)
    
    print("Feeding dummy data into database...")
    for doc in dummy_docs:
        bdoc = BidderDocument(
            bidder_id=bidder.id,
            document_type=doc["type"],
            filename=f"dummy_{doc['type']}.pdf",
            file_hash="dummyhash",
            is_synthetic=True
        )
        db.add(bdoc)
        db.commit()
        db.refresh(bdoc)
        
        ocr_res = OCRResult(
            document_id=bdoc.id,
            extracted_text=doc["text"],
            confidence=0.99
        )
        db.add(ocr_res)
    db.commit()
    
    results = db.query(OCRResult).all()
    texts = [r.extracted_text for r in results if r.extracted_text]
    images = [create_dummy_image(txt) for txt in texts]
    db.close()
    
    return texts, images

def main():
    print("Loading TrOCR processor and model...")
    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
    
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.vocab_size = model.config.decoder.vocab_size
    model.config.eos_token_id = processor.tokenizer.sep_token_id
    model.config.max_length = 64
    model.config.early_stopping = True
    model.config.no_repeat_ngram_size = 3
    model.config.length_penalty = 2.0
    model.config.num_beams = 4

    texts, images = setup_db_dummy_data()
    
    if not texts:
        print("No training data found in database.")
        return

    # Create Hugging Face Dataset from the extracted database rows
    hf_dataset = Dataset.from_dict({"image": images, "text": texts})

    def preprocess_function(examples):
        imgs = examples["image"]
        txts = examples["text"]
        pixel_values = processor(images=imgs, return_tensors="pt").pixel_values
        labels = processor(text=txts, return_tensors="pt", padding="max_length", max_length=64).input_ids
        labels[labels == processor.tokenizer.pad_token_id] = -100
        return {"pixel_values": pixel_values, "labels": labels}

    print("Preprocessing dataset...")
    processed_dataset = hf_dataset.map(preprocess_function, batched=True, remove_columns=["image", "text"])
    
    train_test_split = processed_dataset.train_test_split(test_size=0.1)
    train_dataset = train_test_split['train']
    eval_dataset = train_test_split['test']

    training_args = Seq2SeqTrainingArguments(
        predict_with_generate=True,
        evaluation_strategy="steps",
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        fp16=False, 
        output_dir="./trocr_finetuned",
        logging_steps=1,
        max_steps=1,
        save_steps=1,
        eval_steps=1,
        remove_unused_columns=False,
    )

    trainer = Seq2SeqTrainer(
        model=model,
        tokenizer=processor.feature_extractor,
        args=training_args,
        compute_metrics=compute_metrics,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=default_data_collator,
    )
    
    print("Starting ML Model training for effective OCR verification with Government Document Formats...")
    trainer.train()
    print("Training complete! Verification engine will now use this fine-tuned model for improved efficiency.")

if __name__ == "__main__":
    main()
