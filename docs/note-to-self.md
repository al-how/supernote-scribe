It's working! Doing some testing of different vllms. Try llava next
Llava's no good, nor are the other 8gb vision llms. Qwen3 is the best 
Tested an n8n workflow where i passed the converted text and the OCR and it wasn't as good. 
Tried with a proofer agent, which sorta worked, but also sorta didn't. Better that I set up a evaluation path for all notes. 

## Problems i'm noticing
The "Review" page doesn't do anything when you Delete. 
But it does save it if you manually type it out

I'd like a way to blast the database so i can test from scratch

Ok so next big move:
- first, set up a method to remove the history so i can test from scratch. Then:
- all notes are auto approved if they pass the threshold, but there's a full review/refinement path: 
    - pngs on one size, extracted text (editable) on the other
    - changes are tracked for future improvements